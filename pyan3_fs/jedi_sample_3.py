import jedi
import os
import ast


class JediUtility:
    def __init__(self, project_path):
        self.project_path = os.path.abspath(project_path)
        self.project = jedi.Project(self.project_path)

    def extract_definitions(self, file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()

        script = jedi.Script(code, path=file_path)

        classes = []
        methods = {}
        functions = []
        class_definitions = {}

        # ファイルパスを絶対パスに統一
        abs_file_path = os.path.abspath(file_path)

        for definition in script.get_names(all_scopes=True, definitions=True):
            # 定義が現在のファイルからのものであることを確認
            if definition.module_path is None:
                continue

            same_file = os.path.samefile(definition.module_path, abs_file_path)

            # 定義がインポートされたものでないことを確認
            is_imported = False
            try:
                tree_name = definition._name.tree_name
                if tree_name is None:
                    is_imported = True
                else:
                    if tree_name.type in ("import_name", "import_from"):
                        is_imported = True
                    else:
                        # 親がimport文であるかを確認
                        parent_node = tree_name.parent
                        while parent_node is not None:
                            if parent_node.type in ("import_name", "import_from"):
                                is_imported = True
                                break
                            parent_node = parent_node.parent
            except AttributeError:
                is_imported = True  # tree_nameが取得できない場合はインポートされたものとみなす

            if same_file and not is_imported:
                if definition.type == "class":
                    # 親がモジュールであるクラスのみを対象に
                    parent = definition.parent()
                    if parent is None or parent.type == "module":
                        classes.append(definition.name)
                        methods[definition.name] = []
                        class_definitions[definition.name] = definition
                        # クラス内のメソッドを取得
                        for child in definition.defined_names():
                            if child.type == "function":
                                methods[definition.name].append(child.name)
                    elif parent.type == "class":
                        # ネストされたクラスは無視
                        pass
                elif definition.type == "function":
                    # モジュールレベルの関数を取得
                    parent = definition.parent()
                    if parent is None or parent.type == "module":
                        functions.append(definition.name)

        return classes, methods, functions, class_definitions

    def find_references(self, class_definitions, methods):
        references = {}

        # ターゲットのモジュール名、クラス名、メソッド名を取得
        module_name = None
        target_class_names = list(class_definitions.keys())
        target_names = target_class_names.copy()
        for class_name, method_list in methods.items():
            for method_name in method_list:
                target_names.append(method_name)
        # デバッグ出力：ターゲット名の表示
        print(f"Debug: Target module is '{module_name}'")
        print(f"Debug: Target classes and methods are {target_names}")

        # 全てのPythonファイルを取得
        python_files = self._get_python_files()

        # 各ファイルを解析
        for file_path in python_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    code = f.read()

                # ターゲットがインポートされているかをチェック
                imported_targets = self.get_imported_targets(code, target_class_names)
                if not imported_targets:
                    continue  # インポートされていなければ次のファイルへ

                # デバッグ出力：解析するファイルとインポートされたターゲット
                print(
                    f"Debug: Analyzing file '{file_path}' (imports: {imported_targets})"
                )

                script = jedi.Script(code, path=file_path)

                for name in imported_targets:
                    references.setdefault(name, [])
                    usages = script.get_references(name=name, include_builtins=False)
                    for usage in usages:
                        usage_file = usage.module_path
                        if usage_file is None or usage_file != file_path:
                            continue

                        # 使用箇所の親を取得
                        parent = usage.parent()
                        parent_class = None
                        parent_function = None

                        while parent is not None:
                            if parent.type == "class":
                                parent_class = parent.name
                                break
                            elif parent.type == "function":
                                parent_function = parent.name
                                break
                            parent = parent.parent()

                        references[name].append(
                            {
                                "file": usage_file,
                                "class": parent_class,
                                "function": parent_function,
                                "line": usage.line,
                                "code": usage.get_line_code().strip(),
                            }
                        )
            except Exception as e:
                # デバッグ出力：例外が発生した場合
                print(
                    f"Debug: Exception occurred while analyzing file '{file_path}': {e}"
                )
                pass

        return references

    def get_imported_targets(self, code, target_class_names):
        """
        指定されたコード内でターゲットのクラスや関数がインポートされているかをチェックします。

        :param code: ファイルのコード
        :param target_class_names: チェックするクラス名や関数名のリスト
        :return: インポートされたターゲットのリスト
        """
        imported_targets = set()
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return imported_targets

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                for alias in node.names:
                    if alias.name in target_class_names:
                        imported_targets.add(alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if (
                        alias.asname in target_class_names
                        or alias.name in target_class_names
                    ):
                        imported_targets.add(alias.name)
        return list(imported_targets)

    def _get_python_files(self):
        python_files = []
        for root, _, files in os.walk(self.project_path):
            for file in files:
                if file.endswith(".py"):
                    python_files.append(os.path.join(root, file))
        return python_files


def main():
    PROJECT_PATH = "/Users/sugiyama/clubjt-server/clubjt-impl/clubjt_impl"
    HANDLER_MODULE = "api/user/service/address.py"

    file_path = os.path.join(PROJECT_PATH, HANDLER_MODULE)
    print(f"Analyzing file: {file_path}")

    if not os.path.exists(file_path):
        print(f"Error: File does not exist: {file_path}")
        return

    jedi_util = JediUtility(PROJECT_PATH)
    classes, methods, functions, class_definitions = jedi_util.extract_definitions(
        file_path
    )

    print("\nClasses defined in this file:")
    for cls in classes:
        print(f"- {cls}")

    print("\nMethods defined in this file:")
    for cls, method_list in methods.items():
        for method in method_list:
            print(f"- {cls}.{method}")

    # クラスとメソッドの参照箇所を取得
    references = jedi_util.find_references(class_definitions, methods)

    print("\nReferences:")
    for name, refs in references.items():
        if refs:  # 参照が存在する場合のみ表示
            print(f"\nName: {name}")
            for ref in refs:
                print(
                    f" - File: {ref['file']}, Line: {ref['line']}, Class: {ref['class']}, Function: {ref['function']}"
                )
                print(f"   Code: {ref['code']}")

    print(f"\nJedi version: {jedi.__version__}")


if __name__ == "__main__":
    main()
