import jedi
import os


def extract_file_specific_definitions(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        code = file.read()

    script = jedi.Script(code, path=file_path)

    # Find all lines starting with "class " in the file
    class_lines = set(
        line_num
        for line_num, line in enumerate(code.splitlines(), 1)
        if line.lstrip().startswith("class ")
    )

    classes = []
    methods = {}
    functions = []

    for definition in script.get_names():
        if definition.type == "class" and definition.line in class_lines:
            classes.append(definition.name)
            methods[definition.name] = []
            for child in definition.defined_names():
                if child.type == "function":
                    methods[definition.name].append(child.name)
        elif definition.type == "function":
            if definition.parent().type != "class":
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
