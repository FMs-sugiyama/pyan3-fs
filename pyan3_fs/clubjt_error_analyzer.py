import os
import csv
import logging
import astroid
from collections.abc import Sequence


class ClubjtErrorAnalyzer:
    PROJECT_PATH = "/Users/sugiyama/clubjt-server/clubjt-impl"
    TARGET_MODULE = "clubjt_impl"
    COMMON_ERROR_MESSAGE = "ただいま混み合っております。 " "誠に申し訳ございませんが、しばらくしてからもう一度やり直してください。"
    TARGET_ERRORS = [
        "ClubjtError",
        "ClubjtModuleError",
        "ClubjtAuth0Error",
        "ClubjtAuth0AuthenticationAPIError",
        "ClubjtAuth0ManagementAPIError",
    ]
    OUTPUT_FILE = "clubjt_error_result.csv"

    def __init__(
        self, project_path: str = PROJECT_PATH, target_module: str = TARGET_MODULE
    ) -> None:
        self.project_path = project_path
        self.target_module = target_module
        self.setup_logging()

    @classmethod
    def setup_logging(cls) -> None:
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )

    def execute(self) -> None:
        try:
            results = self.analyze_project()
            self.write_results_to_csv(results)
            logging.info(f"Analysis completed. Results written to {self.OUTPUT_FILE}")
        except Exception as e:
            logging.error(f"An error occurred during execution: {str(e)}")

    def analyze_project(self) -> list[dict]:
        results = []
        try:
            for root, _, files in os.walk(
                os.path.join(self.project_path, self.target_module)
            ):
                for file in files:
                    if file.endswith(".py"):
                        file_path = os.path.join(root, file)
                        results.extend(self.analyze_file(file_path))
        except Exception as e:
            logging.error(f"Error analyzing project: {str(e)}")
        return results

    def analyze_file(self, file_path: str) -> list[dict]:
        results = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            module = astroid.parse(content, path=file_path)
            for node in module.nodes_of_class(astroid.Raise):
                if isinstance(node.exc, astroid.Call):
                    error_class = node.exc.func
                    if isinstance(error_class, astroid.Attribute):
                        error_class = error_class.attrname
                    elif isinstance(error_class, astroid.Name):
                        error_class = error_class.name

                    if error_class in self.TARGET_ERRORS:
                        result = self.extract_error_info(node, file_path)
                        if result:
                            results.append(result)
        except Exception as e:
            logging.error(f"Error analyzing file {file_path}: {str(e)}")
        return results

    def extract_error_info(self, node: astroid.Raise, file_path: str) -> dict:
        try:
            class_name = self.get_class_name(node)
            function_name = self.get_function_name(node)
            error_class_name = self.get_error_class_name(node.exc)
            status_code, detail_code, reason, message = self.get_error_args(node.exc)
            relative_path = os.path.relpath(file_path, self.project_path)

            result = {
                "file_path": relative_path,
                "class_name": class_name,
                "function_name": function_name,
                "error_class_name": error_class_name,
                "status_code": status_code,
                "reason": reason,
                "message": message or self.COMMON_ERROR_MESSAGE,
            }

            if error_class_name == "ClubjtModuleError":
                result["detail_code"] = detail_code

            return result
        except Exception as e:
            logging.error(f"Error extracting error info: {str(e)}")
            return {}

    @classmethod
    def get_class_name(cls, node: astroid.Raise) -> str | None:
        parent = node.parent
        while parent:
            if isinstance(parent, astroid.ClassDef):
                return parent.name
            parent = parent.parent
        return None

    @classmethod
    def get_function_name(cls, node: astroid.Raise) -> str | None:
        parent = node.parent
        while parent:
            if isinstance(parent, astroid.FunctionDef):
                return parent.name
            parent = parent.parent
        return None

    @classmethod
    def get_error_class_name(cls, exc_node: astroid.Call) -> str:
        if isinstance(exc_node.func, astroid.Attribute):
            return exc_node.func.attrname
        elif isinstance(exc_node.func, astroid.Name):
            return exc_node.func.name
        return "Unknown"

    @classmethod
    def get_error_args(
        cls, exc_node: astroid.Call
    ) -> tuple[str | None, str | None, str | None, str | None]:
        status_code = None
        detail_code = None
        reason = None
        message = None

        def extract_value(node: astroid.NodeNG) -> str | None:
            if isinstance(node, astroid.Const):
                return str(node.value)
            elif isinstance(node, astroid.JoinedStr):  # f-string
                return cls.process_fstring(node)
            elif isinstance(node, (astroid.BinOp, astroid.Call)):
                return cls.get_node_source(node)
            return None

        # Process positional arguments
        for idx, arg in enumerate(exc_node.args):
            value = extract_value(arg)
            if idx == 0:
                status_code = value
            elif idx == 1 and cls.get_error_class_name(exc_node) == "ClubjtModuleError":
                detail_code = value
            elif idx == 1 and cls.get_error_class_name(exc_node) != "ClubjtModuleError":
                reason = value
            elif idx == 2 and cls.get_error_class_name(exc_node) == "ClubjtModuleError":
                reason = value
            elif idx == 2 and cls.get_error_class_name(exc_node) != "ClubjtModuleError":
                message = value
            elif idx == 3 and cls.get_error_class_name(exc_node) == "ClubjtModuleError":
                message = value

        # Process keyword arguments
        for keyword in exc_node.keywords:
            value = extract_value(keyword.value)
            if keyword.arg == "status_code":
                status_code = value
            elif keyword.arg == "detail_code":
                detail_code = value
            elif keyword.arg == "reason":
                reason = value
            elif keyword.arg == "message":
                message = value

        return status_code, detail_code, reason, message

    @classmethod
    def process_fstring(cls, node: astroid.JoinedStr) -> str:
        parts = []
        for part in node.values:
            if isinstance(part, astroid.Const):
                parts.append(part.value)
            elif isinstance(part, astroid.FormattedValue):
                parts.append(f"{{{cls.get_node_source(part.value)}}}")
        return "".join(parts)

    @classmethod
    def get_node_source(cls, node: astroid.NodeNG) -> str:
        if isinstance(node, astroid.Name):
            return node.name
        elif isinstance(node, astroid.Attribute):
            return f"{cls.get_node_source(node.expr)}.{node.attrname}"
        elif isinstance(node, astroid.Call):
            func = cls.get_node_source(node.func)
            args = ", ".join(cls.get_node_source(arg) for arg in node.args)
            return f"{func}({args})"
        else:
            return node.as_string()

    def write_results_to_csv(self, results: Sequence[dict]) -> None:
        try:
            fieldnames = [
                "file_path",
                "class_name",
                "function_name",
                "error_class_name",
                "status_code",
                "detail_code",
                "reason",
                "message",
            ]
            with open(self.OUTPUT_FILE, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for result in results:
                    if "detail_code" not in result:
                        result[
                            "detail_code"
                        ] = ""  # Add empty string for non-ClubjtModuleError
                    writer.writerow(result)
        except Exception as e:
            logging.error(f"Error writing results to CSV: {str(e)}")


if __name__ == "__main__":
    analyzer = ClubjtErrorAnalyzer()
    analyzer.execute()
