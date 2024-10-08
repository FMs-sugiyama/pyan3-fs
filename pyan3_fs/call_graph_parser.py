import os
import sys
import astroid
import csv
import traceback
import logging
from pathlib import Path
from astroid.exceptions import AstroidError, InferenceError


class CallGraphAnalyzer:
    PROJECT_PATH = "/Users/sugiyama/clubjt-server/clubjt-impl"
    TARGET_MODULE = "clubjt_impl"
    CSV_FILE = "clubjt_reference_result.csv"

    def __init__(self):
        self.project_path = os.path.abspath(self.PROJECT_PATH)
        self.target_module = self.TARGET_MODULE
        self.target_path = os.path.join(self.project_path, self.target_module)
        self.module_cache = {}
        self.definitions = []
        self.references = []
        self.definition_qnames = set()
        self.builder = astroid.builder.AstroidBuilder()
        self.python_files = []

        # ログの設定
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )
        self.logger = logging.getLogger()

        if self.project_path not in sys.path:
            sys.path.insert(0, self.project_path)

    def execute(self):
        try:
            # 解析対象のPythonファイルを取得（TARGET_MODULE 配下）
            self.python_files = self.get_python_files(self.target_path)
            self.logger.info(f"{len(self.python_files)} 個のPythonファイルから定義を抽出します。")

            # 定義を抽出
            for file_path in self.python_files:
                self.extract_definitions(file_path)

            if not self.definitions:
                self.logger.error("定義が見つかりませんでした。")
                return

            self.definition_qnames = set(defn["qname"] for defn in self.definitions)
            self.logger.info(f"定義を {len(self.definition_qnames)} 件収集しました。")

            # 参照の探索範囲を TARGET_MODULE 配下の Python ファイルとする
            all_python_files = self.get_python_files(self.target_path)
            self.logger.info(f"{len(all_python_files)} 個のPythonファイルを解析します。")

            # 各ファイルで参照を探索
            for file_path in all_python_files:
                self.find_references_in_file(file_path)

            # 結果をCSVに書き込み
            self.write_to_csv()
            self.logger.info(f"解析が完了しました。結果は {self.CSV_FILE} に出力されました。")

        except Exception as e:
            self.logger.error(f"解析中にエラーが発生しました: {e}")
            traceback.print_exc()

    def get_python_files(self, path):
        python_files = []
        for root, dirs, files in os.walk(path):
            # 特定のディレクトリを除外したい場合は、ここで除外できます
            dirs[:] = [d for d in dirs if d != "tests"]  # 'tests' ディレクトリを除外

            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    relative_file_path = os.path.relpath(file_path, self.project_path)
                    python_files.append(relative_file_path)
        return python_files

    def get_module_qname(self, file_path):
        try:
            absolute_path = os.path.join(self.project_path, file_path)
            relative_path = Path(absolute_path).relative_to(self.project_path)
        except ValueError:
            self.logger.error(
                f"ファイル '{file_path}' はプロジェクトパス '{self.project_path}' の下にありません。"
            )
            return None

        parts = relative_path.with_suffix("").parts
        module_name = ".".join(parts)
        return module_name

    def parse_module(self, file_path, module_name):
        absolute_file_path = os.path.join(self.project_path, file_path)
        try:
            if file_path in self.module_cache:
                module = self.module_cache[file_path]
            else:
                module = self.builder.file_build(absolute_file_path, module_name)
                self.module_cache[file_path] = module
            return module
        except (AstroidError, FileNotFoundError, StopIteration) as e:
            self.logger.error(f"モジュール '{file_path}' の解析中にエラーが発生しました: {e}")
            return None

    def extract_definitions(self, file_path):
        module_name = self.get_module_qname(file_path)
        if not module_name:
            return

        module = self.parse_module(file_path, module_name)
        if not module:
            return

        for node in module.body:
            if isinstance(node, astroid.ClassDef):
                self._extract_class_definitions(node, file_path, set())
            elif isinstance(node, astroid.FunctionDef):
                qname = node.qname()
                func_def = {
                    "file_path": file_path,
                    "class_name": None,
                    "function_name": node.name,
                    "qname": qname,
                    "node": node,
                }
                self.definitions.append(func_def)

    def _extract_class_definitions(self, class_node, file_path, processed_classes):
        if class_node.qname() in processed_classes:
            return
        processed_classes.add(class_node.qname())

        qname = class_node.qname()
        class_def = {
            "file_path": file_path,
            "class_name": class_node.name,
            "function_name": None,
            "qname": qname,
            "node": class_node,
        }
        self.definitions.append(class_def)

        # 明示的に定義されたメソッドを取得
        for method in class_node.mymethods():
            qname = method.qname()
            method_def = {
                "file_path": file_path,
                "class_name": class_node.name,
                "function_name": method.name,
                "qname": qname,
                "node": method,
            }
            self.definitions.append(method_def)

        # 継承元クラスを処理
        for base in class_node.bases:
            try:
                inferred_bases = base.infer()
                for inferred_base in inferred_bases:
                    if isinstance(inferred_base, astroid.ClassDef):
                        # 継承元クラスが TARGET_MODULE 内にあるか確認
                        base_module = inferred_base.root()
                        base_module_qname = base_module.name
                        if base_module_qname.startswith(self.target_module):
                            base_file_path = os.path.relpath(
                                base_module.file, self.project_path
                            )
                            self._extract_class_definitions(
                                inferred_base, base_file_path, processed_classes
                            )
            except (InferenceError, AttributeError):
                continue

        # 再帰的に内部クラスを処理
        for subclass in class_node.locals.values():
            for subnode in subclass:
                if isinstance(subnode, astroid.ClassDef):
                    self._extract_class_definitions(
                        subnode, file_path, processed_classes
                    )

    def find_references_in_file(self, file_path):
        module_name = self.get_module_qname(file_path)
        if not module_name:
            return

        module = self.parse_module(file_path, module_name)
        if not module:
            return

        for node in module.nodes_of_class(
            (astroid.Name, astroid.Attribute, astroid.Call)
        ):
            try:
                for inferred in node.infer():
                    if not hasattr(inferred, "qname"):
                        continue
                    inferred_qname = inferred.qname()
                    if inferred_qname in self.definition_qnames:
                        class_name, function_name = self.get_context(node)
                        reference = {
                            "source_file_path": self.get_definition_file_path(
                                inferred_qname
                            ),
                            "source_class_name": self.get_definition_class_name(
                                inferred_qname
                            ),
                            "source_function_name": self.get_definition_function_name(
                                inferred_qname
                            ),
                            "reference_file_path": file_path,
                            "reference_class_name": class_name,
                            "reference_function_name": function_name,
                        }
                        self.references.append(reference)
            except (InferenceError, StopIteration):
                continue
            except Exception as e:
                self.logger.error(f"ファイル {file_path} のノード解析中にエラーが発生しました: {e}")
                continue

    def get_context(self, node):
        class_name = None
        function_name = None
        parent = node.parent
        while parent:
            if isinstance(parent, astroid.FunctionDef):
                function_name = parent.name
                parent = parent.parent
            elif isinstance(parent, astroid.ClassDef):
                class_name = parent.name
                break
            else:
                parent = parent.parent
        return class_name, function_name

    def get_definition_file_path(self, qname):
        for defn in self.definitions:
            if defn["qname"] == qname:
                return defn["file_path"]
        return ""

    def get_definition_class_name(self, qname):
        for defn in self.definitions:
            if defn["qname"] == qname:
                return defn["class_name"] or ""
        return ""

    def get_definition_function_name(self, qname):
        for defn in self.definitions:
            if defn["qname"] == qname:
                return defn["function_name"] or ""
        return ""

    def write_to_csv(self):
        fieldnames = [
            "source_file_path",
            "source_class_name",
            "source_function_name",
            "reference_file_path",
            "reference_class_name",
            "reference_function_name",
        ]
        written_rows = set()  # 重複を防ぐためのセット

        with open(self.CSV_FILE, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            # 参照があるもののみを出力
            for reference in self.references:
                row = (
                    reference["source_file_path"],
                    reference["source_class_name"],
                    reference["source_function_name"],
                    reference["reference_file_path"],
                    reference["reference_class_name"] or "",
                    reference["reference_function_name"] or "",
                )
                if row not in written_rows:
                    writer.writerow(
                        {
                            "source_file_path": reference["source_file_path"],
                            "source_class_name": reference["source_class_name"],
                            "source_function_name": reference["source_function_name"],
                            "reference_file_path": reference["reference_file_path"],
                            "reference_class_name": reference["reference_class_name"]
                            or "",
                            "reference_function_name": reference[
                                "reference_function_name"
                            ]
                            or "",
                        }
                    )
                    written_rows.add(row)


if __name__ == "__main__":
    analyzer = CallGraphAnalyzer()
    analyzer.execute()
