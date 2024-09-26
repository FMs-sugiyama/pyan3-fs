import os
import csv
import ast


class CallTreeParser:
    def __init__(self, project_path, entry_module, output_file):
        self.project_path = os.path.abspath(project_path)
        self.entry_module = entry_module
        self.output_file = output_file
        self.endpoints = []
        self.call_graph = {}
        self.all_data = []
        self.visited = set()

    def execute(self):
        self.find_endpoint_functions()
        for module_name, func_name in self.endpoints:
            self.traverse_calls(module_name, func_name, depth=0)
        self.write_csv()

    def find_endpoint_functions(self):
        """エントリモジュールからFastAPIのエンドポイント関数を探します。"""
        module_file = self.module_to_file(self.entry_module)
        if not module_file:
            print(f"モジュール {self.entry_module} が見つかりません。")
            return
        with open(module_file, "r", encoding="utf-8") as f:
            source_code = f.read()
        tree = ast.parse(source_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.decorator_list:
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Call) and isinstance(
                            decorator.func, ast.Attribute
                        ):
                            if (
                                decorator.func.value.id == "api"
                                and decorator.func.attr
                                in ["get", "post", "put", "delete", "patch"]
                            ):
                                func_name = node.name
                                self.endpoints.append((self.entry_module, func_name))

    def module_to_file(self, module_name):
        """モジュール名をファイルパスに変換します。"""
        module_rel_path = module_name.replace(".", os.sep) + ".py"
        file_path = os.path.join(self.project_path, module_rel_path)
        return file_path if os.path.exists(file_path) else ""

    def traverse_calls(self, module_name, func_name, depth):
        full_name = f"{module_name}.{func_name}"
        if full_name in self.visited:
            return
        self.visited.add(full_name)
        file_path = self.module_to_file(module_name)
        self.all_data.append(
            {
                "file_path": file_path,
                "module_name": module_name,
                "class_name": "",
                "function_name": func_name,
                "depth": depth,
            }
        )

        if not file_path:
            return

        with open(file_path, "r", encoding="utf-8") as f:
            source_code = f.read()

        tree = ast.parse(source_code)
        function_node = self.find_function_node(tree, func_name)
        if function_node:
            calls = self.find_function_calls(function_node)
            for call in calls:
                called_func_name = call.split(".")[-1]
                called_module_name = module_name  # 簡略化のため同一モジュール内と仮定
                self.traverse_calls(called_module_name, called_func_name, depth + 1)

    def find_function_node(self, tree, func_name):
        """関数定義ノードを探します。"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                return node
        return None

    def find_function_calls(self, node):
        """関数内の関数呼び出しを取得します。"""
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)
        return calls

    def write_csv(self):
        """結果を CSV ファイルに書き込みます。"""
        fieldnames = [
            "file_path",
            "module_name",
            "class_name",
            "function_name",
            "depth",
        ]
        with open(self.output_file, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in self.all_data:
                writer.writerow(row)


def main():
    project_path = (
        "/Users/sugiyama/clubjt-server/clubjt-impl"  # input("プロジェクトのパスを入力してください: ")
    )
    entry_module = (
        "clubjt_impl.api.user_handler"  # input("エントリモジュールを入力してください（例: app.main）: ")
    )
    output_file = "./test.csv"
    parser = CallTreeParser(project_path, entry_module, output_file)
    parser.execute()
    print(f"呼び出し階層データが {output_file} に書き込まれました。")


if __name__ == "__main__":
    main()
