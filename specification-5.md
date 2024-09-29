以下の要件を満たす完全で実行可能なPythonコードを生成してください：

1. astroidを使用してPythonコードの静的解析を行う、CallGraphAnalyzerという名前のクラスを実装してください。

2. 主な機能：
   - PROJECT_PATHで指定されたPythonプロジェクトの、TARGET_MODULE配下の全ての.pyファイルを走査します。
   - ソースコード内で定義されたfunction/class/class method(クラス内のfunction）を抽出します
     - 抽出のコードは別途提供されるコードを参考にして作成してください。そちらである程度出来上がったものがあります
   - 抽出した各function/class/class methodについて、以下の情報を抽出します：
     a) 発生元情報：file_path（PROJECT_PATHからの相対パス）, class_name（クラスメソッドの場合、そうでなければNull）, function_name
     b) 参照先情報：file_path（PROJECT_PATHからの相対パス）, class_name（クラスメソッドの場合、そうでなければNull）, function_name
     - カラム名はわかりやすく設定してください
   - 抽出した情報をCSVファイル（clubjt_reference_result.csv）に出力します。
   - 多数のファイルを解析するため、もしファイルごとのastroidの解析結果をキャッシュして使える要素があれば、キャッシュでの動作も考慮します。

3. 実装詳細：
   - executeメソッドを実装し、このメソッドから解析を開始します。

4. 定数：
   - PROJECT_PATH = "/Users/sugiyama/clubjt-server/clubjt-impl"
   - TARGET_MODULE = "clubjt_impl"

5. コーディング規約：
   - Python 3.10以上と互換性のあるコードを記述してください。
   - 関数とメソッドに明確な型アノテーションを使用し、組み込み型のみを使用してください（typingモジュールは使用しない）。
   - PEP 8スタイルガイドラインに準拠してください。
   - 綿密なエラー処理とログ記録を実装してください。
   - 静的メソッドの代わりに@classmethodデコレータを使用してください。

6. コードは__main__から実行されるようにしてください。

省略のない、完全で実行可能なPythonコードファイルを生成してください。非現実的または機能しないソリューションは避けてください。

7. エラー調整

- CSVのカラムが全て揃っていないケースがあるようです。必ず全量の出力を（値なしでも空欄で）してください
- 「参照先」の定義は、あるファイルで抽出したclass/function(class method)を他のモジュールから利用した箇所の情報です。以下のような結果が出ているのですが、扱いに誤りがありそうです

```csv
clubjt_impl/rds_entity_base.py,CommonEntity,,class_definition,,,
clubjt_impl/rds_entity_base.py,CommonEntity,datetime,name_reference,/Users/sugiyama/homebrew/Cellar/python@3.11/3.11.0/Frameworks/Python.framework/Versions/3.11/lib/python3.11/datetime.py,,datetime
clubjt_impl/rds_entity_base.py,CommonEntity,str,name_reference,,,str
clubjt_impl/rds_entity_base.py,CommonEntity,datetime,name_reference,/Users/sugiyama/homebrew/Cellar/python@3.11/3.11.0/Frameworks/Python.framework/Versions/3.11/lib/python3.11/datetime.py,,datetime
clubjt_impl/rds_entity_base.py,CommonEntity,str,name_reference,,,str
clubjt_impl/rds_entity_base.py,CommonEntity,bool,name_reference,,,bool
clubjt_impl/rds_entity_base.py,CommonEntity,int,name_reference,,,int

```
- 

8. 参考コード

```python
import astroid
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from astroid.exceptions import AstroidError, InferenceError
from pathlib import Path
from astroid.builder import AstroidBuilder


class FileParser:
    def __init__(
        self,
        project_path: str,
        handler_module: str,
        scan_module: str = None,
        max_workers: int = 4,
        output_file: str = "references_output.txt",
    ):
        self.project_path = os.path.abspath(project_path)
        self.handler_module = handler_module
        self.handler_module_path = os.path.join(self.project_path, self.handler_module)
        self.scan_module = scan_module
        self.max_workers = max_workers
        self.output_file = output_file
        self.total_files = 0
        self.files_with_stop_iteration = 0

        try:
            self.output_fp = open(self.output_file, "w", encoding="utf-8")
        except IOError as e:
            print(f"Error opening output file '{self.output_file}': {e}")
            sys.exit(1)
        self.write = self.output_fp.write

        self.write(f"Handler module path: {self.handler_module_path}\n")

        if not os.path.isfile(self.handler_module_path):
            self.write(
                f"Error: Handler module '{self.handler_module_path}' does not exist.\n"
            )
            self.output_fp.close()
            sys.exit(1)

        if self.project_path not in sys.path:
            sys.path.insert(0, self.project_path)

        self.builder = AstroidBuilder()

    def __del__(self):
        if hasattr(self, "output_fp") and not self.output_fp.closed:
            self.output_fp.close()

    def get_module_qname(self, file_path):
        try:
            relative_path = Path(file_path).relative_to(self.project_path)
        except ValueError:
            self.write(
                f"Error: File '{file_path}' is not under project path '{self.project_path}'.\n"
            )
            return None

        parts = relative_path.with_suffix("").parts
        module_name = ".".join(parts)
        self.write(f"Derived module name for '{file_path}': {module_name}\n")
        return module_name

    def find_references_in_file(self, file_path: str, def_qnames: set):
        self.total_files += 1
        references = []
        try:
            module_name = self.get_module_qname(file_path)
            if not module_name:
                return references
            module = self.builder.file_build(file_path, module_name)
        except (AstroidError, FileNotFoundError, StopIteration) as e:
            self.write(f"Error parsing file '{file_path}': {e}\n")
            return references

        def get_parent_info(node):
            class_name = ""
            function_name = ""
            parent = node.parent
            while parent:
                if isinstance(parent, astroid.ClassDef):
                    class_name = parent.name
                    break
                elif isinstance(parent, astroid.FunctionDef):
                    if not function_name:  # Only set if not already set
                        function_name = parent.name
                    if isinstance(parent.parent, astroid.ClassDef):
                        class_name = parent.parent.name
                        break
                parent = parent.parent
            return class_name, function_name

        for node in module.nodes_of_class((astroid.Name, astroid.Attribute)):
            try:
                inferred_defs = list(node.infer())
            except (InferenceError, StopIteration):
                self.files_with_stop_iteration += 1
                continue

            for inferred_def in inferred_defs:
                try:
                    inferred_qname = inferred_def.qname()
                except (StopIteration, AttributeError):
                    continue

                if (
                    inferred_qname
                    and inferred_qname.startswith("clubjt_impl.")
                    and inferred_qname in def_qnames
                ):
                    class_name, function_name = get_parent_info(node)
                    reference_info = {
                        "name": node.as_string(),
                        "file": file_path,
                        "line": node.lineno,
                        "column": node.col_offset,
                        "class_name": class_name or "N/A",
                        "function_name": function_name or "N/A",
                    }
                    references.append(reference_info)
                    self.write(
                        f"Reference found: {reference_info['name']} in {reference_info['file']} "
                        f"at line {reference_info['line']}, column {reference_info['column']}, "
                        f"class: {reference_info['class_name']}, method/function: {reference_info['function_name']}\n"
                    )

        return references

    def run(self):
        try:
            module_a_qname = self.get_module_qname(self.handler_module_path)
            if not module_a_qname:
                self.write(
                    f"Error: Could not derive module name for '{self.handler_module_path}'.\n"
                )
                self.output_fp.close()
                sys.exit(1)
            module_a = self.builder.file_build(self.handler_module_path, module_a_qname)
            self.write("Parsing succeeded.\n")
            self.write(f"module_a qname: {module_a.qname()}\n")
            self.write(f"module_a type: {type(module_a)}\n")
            self.write(f"module_a attributes: {dir(module_a)}\n")
        except (AstroidError, FileNotFoundError) as e:
            self.write(f"Error parsing module '{self.handler_module_path}': {e}\n")
            self.output_fp.close()
            sys.exit(1)
        except StopIteration as e:
            self.write(
                f"StopIteration when building module '{self.handler_module_path}': {e}\n"
            )
            self.output_fp.close()
            sys.exit(1)
        except Exception as e:
            self.write(
                f"Unexpected error when building module '{self.handler_module_path}': {e}\n"
            )
            self.write(traceback.format_exc())
            self.output_fp.close()
            sys.exit(1)

        try:
            definitions = []
            for node in module_a.body:
                if isinstance(node, astroid.ClassDef):
                    definitions.append(node)
                    methods = list(node.methods())
                    definitions.extend(methods)
                elif isinstance(node, astroid.FunctionDef):
                    definitions.append(node)
            self.write(f"Found {len(definitions)} classes/functions/methods.\n")
            self.write("Definitions:\n")
            for defn in definitions:
                self.write(f" - {defn.qname()} ({defn.__class__.__name__})\n")
        except AttributeError as e:
            self.write(f"Error accessing classes or functions: {e}\n")
            self.write(f"module_a type: {type(module_a)}\n")
            self.write(f"module_a attributes: {dir(module_a)}\n")
            self.output_fp.close()
            sys.exit(1)
        except Exception as e:
            self.write(f"Unexpected error when accessing definitions: {e}\n")
            self.write(traceback.format_exc())
            self.output_fp.close()
            sys.exit(1)

        if not definitions:
            self.write(
                f"No classes or functions found in '{self.handler_module_path}'.\n"
            )
            self.output_fp.close()
            return

        def_qnames = set()
        for defn in definitions:
            qname = defn.qname()
            if qname and qname.startswith("clubjt_impl."):
                def_qnames.add(qname)
                self.write(f"Definition QNAME: {qname}\n")

        if self.scan_module:
            scan_path = os.path.join(self.project_path, self.scan_module)
            if not os.path.isdir(scan_path):
                self.write(
                    f"Error: Scan module '{self.scan_module}' does not exist under project path.\n"
                )
                self.output_fp.close()
                sys.exit(1)
            py_files = [
                os.path.join(root, file)
                for root, dirs, files in os.walk(scan_path)
                for file in files
                if file.endswith(".py")
                and os.path.abspath(os.path.join(root, file))
                != os.path.abspath(self.handler_module_path)
            ]
        else:
            py_files = [
                os.path.join(root, file)
                for root, dirs, files in os.walk(self.project_path)
                for file in files
                if file.endswith(".py")
                and os.path.abspath(os.path.join(root, file))
                != os.path.abspath(self.handler_module_path)
            ]

        self.write(f"Scanning {len(py_files)} Python files for references...\n")

        references = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {
                executor.submit(
                    self.find_references_in_file, file_path, def_qnames
                ): file_path
                for file_path in py_files
            }
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    file_refs = future.result()
                    references.extend(file_refs)
                except StopIteration as e:
                    self.write(
                        f"StopIteration raised without any error information in file '{file_path}': {e}\n"
                    )
                except Exception as e:
                    self.write(f"Error processing file '{file_path}': {e}\n")
                    self.write(traceback.format_exc())

        if references:
            self.write(
                f"\nReferences to definitions in '{self.handler_module}' found:\n"
            )
            for ref in references:
                self.write(
                    f" - {ref['name']} is referenced in {ref['file']} at line {ref['line']}, column {ref['column']}, "
                    f"in class {ref['class_name']}, method/function {ref['function_name']}\n"
                )
        else:
            self.write(
                f"\nNo references to definitions in '{self.handler_module}' were found.\n"
            )

        self.write(
            f"\nAnalysis complete. Total files: {self.total_files}, Files with StopIteration: {self.files_with_stop_iteration}\n"
        )
        self.output_fp.close()


if __name__ == "__main__":
    PROJECT_PATH = "/Users/sugiyama/clubjt-server/clubjt-impl"
    HANDLER_MODULE = "clubjt_impl/api/user/service/address.py"
    SCAN_MODULE = "clubjt_impl"
    OUTPUT_FILE = "references_output.txt"

    parser = FileParser(
        project_path=PROJECT_PATH,
        handler_module=HANDLER_MODULE,
        scan_module=SCAN_MODULE,
        max_workers=2,
        output_file=OUTPUT_FILE,
    )
    parser.run()

    print(f"参照結果は '{OUTPUT_FILE}' に出力されました。")


```