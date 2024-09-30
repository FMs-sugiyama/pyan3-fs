import os
import logging
import duckdb


class CallGraphCreator:
    def __init__(self, csv_file, output_file, start_file, start_class, start_function):
        self.csv_file = csv_file
        self.output_file = output_file
        self.start_file = start_file
        self.start_class = start_class
        self.start_function = start_function
        self.conn = duckdb.connect(":memory:")
        self.logger = self._setup_logger()
        self.call_tree = {}

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
            self._build_call_tree()
            self._write_call_tree()
        except Exception as e:
            self.logger.error(f"An error occurred: {str(e)}")
        finally:
            self.conn.close()

    def _load_csv_to_duckdb(self):
        self.logger.info("Loading CSV to DuckDB")
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
            COPY ref_table FROM '{self.csv_file}' (HEADER, DELIMITER ',')
        """
        )

        result = self.conn.execute("SELECT COUNT(*) FROM ref_table").fetchone()
        self.logger.debug(f"Loaded {result[0]} rows into ref_table")

    def _build_call_tree(self):
        self.logger.info("Building call tree")
        start_point = (self.start_file, self.start_class, self.start_function)
        self._find_callers(start_point, set())

    def _find_callers(self, called, visited):
        if called in visited:
            return
        visited.add(called)

        query = """
            SELECT DISTINCT caller_file_path, caller_class_name, caller_function_name
            FROM ref_table
            WHERE called_file_path = ?
              AND called_class_name = ?
              AND called_function_name = ?
              AND caller_file_path NOT LIKE '%test_%'
        """
        params = [called[0], called[1], called[2]]

        self.logger.debug(f"Executing query with params: {params}")
        result = self.conn.execute(query, params).fetchall()
        self.logger.debug(f"Query returned {len(result)} results")

        callers = []
        for row in result:
            caller = (row[0], row[1] or "None", row[2] or "None")
            callers.append(caller)
            self._find_callers(caller, visited.copy())

        if callers:
            self.call_tree[called] = callers

    def _write_call_tree(self):
        self.logger.info("Writing call tree")
        start_point = (self.start_file, self.start_class, self.start_function)
        with open(self.output_file, "w") as f:
            call_stack = self._get_call_stack(start_point)
            for i, node in enumerate(reversed(call_stack)):
                indent = "  " * i
                f.write(f"{indent}{node[0]}, {node[1]}, {node[2]}\n")

    def _get_call_stack(self, node, visited=None):
        if visited is None:
            visited = set()
        if node in visited:
            return []
        visited.add(node)

        stack = [node]
        if node in self.call_tree:
            for caller in self.call_tree[node]:
                stack.extend(self._get_call_stack(caller, visited))
        return stack


def main():
    csv_file = "clubjt_reference_result.csv"
    output_file = "call_graph.txt"
    start_file = "clubjt_impl/util/user_util.py"
    start_class = "UserUtil"
    start_function = "judge_next_rank_change"

    creator = CallGraphCreator(
        csv_file, output_file, start_file, start_class, start_function
    )
    creator.execute()


if __name__ == "__main__":
    main()
