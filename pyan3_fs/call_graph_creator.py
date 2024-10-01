import os
import logging
import duckdb
import csv
from collections import defaultdict
from itertools import groupby

from pyan3_fs.fastapi_endpoint_datasouce import FastApiEndpointDatasource


class CallGraphCreator:
    def __init__(
        self,
        reference_csv,
        start_points_csv,
        output_file,
        new_output_csv,
        fastapi_endpoints_csv,
    ):
        self.reference_csv = reference_csv
        self.start_points_csv = start_points_csv
        self.output_file = output_file
        self.new_output_csv = new_output_csv
        self.fastapi_endpoints_csv = fastapi_endpoints_csv
        self.conn = duckdb.connect(":memory:")
        self.logger = self._setup_logger()
        self.call_graph = defaultdict(set)
        self.handler_error_mappings = []
        self.error_details = {}
        self.fastapi_endpoints = []

    @classmethod
    def _setup_logger(cls):
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def execute(self):
        try:
            self._load_csv_to_duckdb()
            self._load_fastapi_endpoints()
            start_points = self._load_start_points()
            self._build_call_graph()
            self._write_call_graphs(start_points)
            self._write_handler_error_mapping()
        except Exception as e:
            self.logger.error(f"An error occurred: {str(e)}")
        finally:
            self.conn.close()

    def _load_csv_to_duckdb(self):
        self.logger.info("Loading reference CSV to DuckDB")
        self.conn.execute(
            """
            CREATE TABLE ref_table (
                called_file_path VARCHAR,
                called_class_name VARCHAR,
                called_function_name VARCHAR,
                caller_file_path VARCHAR,
                caller_class_name VARCHAR,
                caller_function_name VARCHAR
            )
        """
        )
        self.conn.execute(
            f"""
            COPY ref_table FROM '{self.reference_csv}' (HEADER, DELIMITER ',')
        """
        )

        result = self.conn.execute("SELECT COUNT(*) FROM ref_table").fetchone()
        self.logger.debug(f"Loaded {result[0]} rows into ref_table")

    def _load_fastapi_endpoints(self):
        self.logger.info("Loading FastAPI endpoints")
        with FastApiEndpointDatasource(self.fastapi_endpoints_csv) as datasource:
            self.fastapi_endpoints = datasource.get_endpoints()
        self.logger.debug(f"Loaded {len(self.fastapi_endpoints)} FastAPI endpoints")

    def _load_start_points(self):
        self.logger.info("Loading start points and error details from CSV")
        start_points = []
        with open(self.start_points_csv, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row["file_path"], row["class_name"], row["function_name"])
                start_points.append(key)
                self.error_details[key] = {
                    "error_class_name": row.get("error_class_name", ""),
                    "status_code": row.get("status_code", ""),
                    "reason": row.get("reason", ""),
                    "message": row.get("message", ""),
                }
        self.logger.debug(f"Loaded {len(start_points)} start points")
        return start_points

    def _build_call_graph(self):
        self.logger.info("Building complete call graph")
        query = """
            SELECT DISTINCT
                called_file_path, called_class_name, called_function_name,
                caller_file_path, caller_class_name, caller_function_name
            FROM ref_table
            WHERE caller_file_path NOT LIKE '%test_%'
        """
        result = self.conn.execute(query).fetchall()

        for row in result:
            called = (row[0], row[1] or "", row[2])
            caller = (row[3], row[4] or "", row[5])
            self.call_graph[called].add(caller)

    def _write_call_graphs(self, start_points):
        with open(self.output_file, "w") as out_file:
            for i, start_point in enumerate(start_points):
                self.logger.debug(
                    f"Processing start point {i + 1}/{len(start_points)}: {start_point}"
                )
                out_file.write(
                    f"Start Point: {start_point[0]}, {start_point[1]}, {start_point[2]}\n"
                )
                self._traverse_and_write_call_tree(start_point, out_file)
                out_file.write(
                    "\n" + "=" * 50 + "\n\n"
                )  # Separator between call graphs

    def _traverse_and_write_call_tree(
        self, node, out_file, visited=None, current_path=None
    ):
        if visited is None:
            visited = set()
        if current_path is None:
            current_path = []

        if node in visited:
            return
        visited.add(node)

        current_path.append(node)

        if node[0].endswith("_handler.py") or not self.call_graph[node]:
            self._write_call_stack(list(reversed(current_path)), out_file)
        else:
            for caller in sorted(self.call_graph[node]):
                self._traverse_and_write_call_tree(
                    caller, out_file, visited.copy(), current_path.copy()
                )

        current_path.pop()

    def _write_call_stack(self, call_stack, out_file):
        handler = None
        for i, node in enumerate(call_stack):
            indent = "  " * i
            class_name = f", {node[1]}" if node[1] else ""
            out_file.write(f"{indent}{node[0]}{class_name}, {node[2]}\n")

            if node[0].endswith("_handler.py"):
                handler = node

            if handler and i == len(call_stack) - 1:
                error_info = self.error_details.get(node, {})
                handler_module = os.path.basename(handler[0])[:-3]  # Remove '.py'
                if handler_module in ["user_handler", "operator_handler"]:
                    endpoint = next(
                        (
                            ep
                            for ep in self.fastapi_endpoints
                            if ep.module_name == handler_module
                            and ep.operation_id == handler[2]
                        ),
                        None,
                    )
                    if endpoint:
                        self.handler_error_mappings.append(
                            {
                                "module": endpoint.module_name,
                                "http_method": endpoint.http_method,
                                "path": endpoint.path,
                                "operation_id": endpoint.operation_id,
                                "file_path": node[0],
                                "class_name": node[1],
                                "function_name": node[2],
                                "error_class_name": error_info.get(
                                    "error_class_name", ""
                                ),
                                "status_code": error_info.get("status_code", ""),
                                "reason": error_info.get("reason", ""),
                                "message": error_info.get("message", ""),
                            }
                        )

    def _write_handler_error_mapping(self):
        self.logger.info("Writing handler-error mapping to CSV")
        fieldnames = [
            "module",
            "http_method",
            "path",
            "operation_id",
            "file_path",
            "class_name",
            "function_name",
            "error_class_name",
            "status_code",
            "reason",
            "message",
        ]

        # Sort the mappings based on the order in fastapi_endpoints
        endpoint_order = {
            (ep.module_name, ep.operation_id): i
            for i, ep in enumerate(self.fastapi_endpoints)
        }
        sorted_mappings = sorted(
            self.handler_error_mappings,
            key=lambda x: (
                endpoint_order.get((x["module"], x["operation_id"]), float("inf")),
                x["module"],
            ),
        )

        # Remove duplicates while preserving order
        unique_mappings = []
        seen = set()
        for mapping in sorted_mappings:
            key = (
                mapping["module"],
                mapping["operation_id"],
                mapping["error_class_name"],
                mapping["status_code"],
                mapping["reason"],
                mapping["message"],
            )
            if key not in seen:
                seen.add(key)
                unique_mappings.append(mapping)

        with open(self.new_output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(fieldnames)

            for module, group in groupby(unique_mappings, key=lambda x: x["module"]):
                for mapping in group:
                    writer.writerow([mapping[field] for field in fieldnames])
                writer.writerow([])  # Add a blank line between modules


def main():
    reference_csv = "clubjt_reference_result.csv"
    start_points_csv = "clubjt_error_result.csv"
    output_file = "call_graphs.txt"
    new_output_csv = "handler_error_mapping.csv"
    fastapi_endpoints_csv = "fastapi_endpoints.csv"

    creator = CallGraphCreator(
        reference_csv,
        start_points_csv,
        output_file,
        new_output_csv,
        fastapi_endpoints_csv,
    )
    creator.execute()


if __name__ == "__main__":
    main()
