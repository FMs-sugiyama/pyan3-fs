import astroid
import csv
import os

PROJECT_PATH = "/Users/sugiyama/clubjt-server/clubjt-impl"
TARGET_HANDLER_FILES = [
    "clubjt_impl/api/user_handler.py",
    "clubjt_impl/api/operator_handler.py",
]


class OperatorParser:
    def __init__(self, project_path, target_handler_files):
        self.project_path = project_path
        self.target_handler_files = target_handler_files
        self.output_file = "fastapi_endpoints.csv"

    def parse_fastapi_endpoints(self, file_path):
        with open(file_path, "r") as file:
            content = file.read()

        module = astroid.parse(content)
        endpoints = []
        module_name = os.path.splitext(os.path.basename(file_path))[0]

        for node in module.body:
            if isinstance(node, astroid.FunctionDef):
                if node.decorators:
                    for decorator in node.decorators.nodes:
                        if isinstance(decorator, astroid.Call) and isinstance(
                            decorator.func, astroid.Attribute
                        ):
                            if decorator.func.attrname in [
                                "get",
                                "post",
                                "put",
                                "delete",
                                "patch",
                                "options",
                                "head",
                            ]:
                                http_method = decorator.func.attrname.upper()
                                path = decorator.args[0].value if decorator.args else ""
                                operation_id = node.name
                                endpoints.append(
                                    (module_name, http_method, path, operation_id)
                                )

        return endpoints

    def write_to_csv(self, all_endpoints):
        with open(self.output_file, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["module_name", "http_method", "path", "operation_id"])
            writer.writerows(all_endpoints)

    def execute(self):
        all_endpoints = []
        for handler_file in self.target_handler_files:
            file_path = os.path.join(self.project_path, handler_file)
            try:
                endpoints = self.parse_fastapi_endpoints(file_path)
                all_endpoints.extend(endpoints)
            except Exception as e:
                print(f"Error processing file {file_path}: {str(e)}")

        if all_endpoints:
            self.write_to_csv(all_endpoints)
            print(
                f"CSV file '{self.output_file}' has been generated with data from all handler files."
            )
        else:
            print("No endpoints were found. CSV file was not generated.")


def main():
    parser = OperatorParser(PROJECT_PATH, TARGET_HANDLER_FILES)
    parser.execute()


if __name__ == "__main__":
    main()
