import jedi
import os


def extract_file_specific_definitions(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        code = file.read()

    script = jedi.Script(code, path=file_path)

    classes = []
    methods = {}
    functions = []

    # ファイルパスを絶対パスに統一
    abs_file_path = os.path.abspath(file_path)

    for definition in script.get_names(all_scopes=True, definitions=True):
        # 定義が現在のファイルからのものであることを確認
        same_file = False
        if definition.module_path:
            try:
                same_file = os.path.samefile(definition.module_path, abs_file_path)
            except FileNotFoundError:
                pass  # ファイルが存在しない場合は無視

        # 定義がimportされたものかを判定
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
            is_imported = True  # tree_nameが取得できない場合はimportされたものとみなす

        # 定義が現在のファイルからのものであり、かつimportされたものでないことを確認
        if same_file and not is_imported:
            if definition.type == "class":
                # 親がモジュールであるクラスのみを対象に
                parent = definition.parent()
                parent_type = parent.type if parent else "None"
                if parent_type == "module":
                    classes.append(definition.name)
                    methods[definition.name] = []
                    for child in definition.defined_names():
                        if child.type == "function":
                            methods[definition.name].append(child.name)
            elif definition.type == "function":
                # 親がモジュールである関数のみを対象に
                parent = definition.parent()
                parent_type = parent.type if parent else "None"
                if parent_type == "module":
                    functions.append(definition.name)

    return classes, methods, functions


def main():
    PROJECT_PATH = "/Users/sugiyama/clubjt-server/clubjt-impl"
    HANDLER_MODULE = "clubjt_impl/api/user/service/address.py"

    file_path = os.path.join(PROJECT_PATH, HANDLER_MODULE)
    print(f"Analyzing file: {file_path}")

    if not os.path.exists(file_path):
        print(f"Error: File does not exist: {file_path}")
        return

    classes, methods, functions = extract_file_specific_definitions(file_path)

    print("\nClasses defined in this file:")
    for cls in classes:
        print(f"- {cls}")

    print("\nMethods defined in this file:")
    for cls, method_list in methods.items():
        for method in method_list:
            print(f"- {cls}.{method}")

    print("\nFunctions defined in this file:")
    for func in functions:
        print(f"- {func}")

    print(f"\nJedi version: {jedi.__version__}")


if __name__ == "__main__":
    main()
