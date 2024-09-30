import os
import logging
import duckdb
import csv
from collections import defaultdict


class CallGraphCreator:
    def __init__(self, reference_csv, start_points_csv, output_file):
        self.reference_csv = reference_csv
        self.start_points_csv = start_points_csv
        self.output_file = output_file
        self.conn = duckdb.connect(":memory:")
        self.logger = self._setup_logger()
        self.call_graph = defaultdict(set)

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
            start_points = self._load_start_points()
            self._build_call_graph()
            self._write_call_graphs(start_points)
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

    def _load_start_points(self):
        self.logger.info("Loading start points from CSV")
        start_points = []
        with open(self.start_points_csv, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                start_points.append(
                    (row["file_path"], row["class_name"], row["function_name"])
                )
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
        for i, node in enumerate(call_stack):
            indent = "  " * i
            class_name = f", {node[1]}" if node[1] else ""
            out_file.write(f"{indent}{node[0]}{class_name}, {node[2]}\n")


def main():
    reference_csv = "clubjt_reference_result.csv"
    start_points_csv = "clubjt_error_result.csv"
    output_file = "call_graphs.txt"

    creator = CallGraphCreator(reference_csv, start_points_csv, output_file)
    creator.execute()


if __name__ == "__main__":
    main()
