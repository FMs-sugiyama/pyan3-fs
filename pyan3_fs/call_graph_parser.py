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
    HANDLER_MODULE = "clubjt_impl/api/user/service/address.py"
    CSV_FILE = "clubjt_reference_result.csv"

    def __init__(self):
        self.project_path = os.path.abspath(self.PROJECT_PATH)
        self.target_module = self.TARGET_MODULE
        self.handler_module = self.HANDLER_MODULE
        self.handler_module_path = os.path.join(self.project_path, self.handler_module)
        self.target_path = os.path.join(self.project_path, self.target_module)
        self.module_cache = {}
        self.definitions = []
        self.references = []
        self.definition_qnames = set()
        self.builder = astroid.builder.AstroidBuilder()

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
            # ハンドラーモジュールから定義を抽出
            module_name = self.get_module_qname(self.handler_module_path)
            if not module_name:
                self.logger.error("モジュール名を取得できませんでした。")
                return

            module = self.parse_module(self.handler_module_path, module_name)
            if not module:
                self.logger.error("モジュールの解析に失敗しました。")
                return

            self.extract_definitions(module)

            if not self.definitions:
                self.logger.error("定義が見つかりませんでした。")
                return

            self.definition_qnames = set(defn["qname"] for defn in self.definitions)
            self.logger.info(f"定義を {len(self.definition_qnames)} 件収集しました。")

            # 解析対象のPythonファイルを取得（プロジェクト全体）
            python_files = self.get_python_files()
            self.logger.info(f"{len(python_files)} 個のPythonファイルを解析します。")

            # 各ファイルで参照を探索
            for file_path in python_files:
                self.find_references_in_file(file_path)

            # 結果をCSVに書き込み
            self.write_to_csv()
            self.logger.info(f"解析が完了しました。結果は {self.CSV_FILE} に出力されました。")

        except Exception as e:
            self.logger.error(f"解析中にエラーが発生しました: {e}")
            traceback.print_exc()

    def get_python_files(self):
        python_files = []
        for root, dirs, files in os.walk(self.target_path):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    relative_file_path = os.path.relpath(file_path, self.project_path)
                    python_files.append(relative_file_path)
        return python_files

    def get_module_qname(self, file_path):
        try:
            relative_path = Path(file_path).relative_to(self.project_path)
        except ValueError:
            self.logger.error(
                f"ファイル '{file_path}' はプロジェクトパス '{self.project_path}' の下にありません。"
            )
            return None

        parts = relative_path.with_suffix("").parts
        module_name = ".".join(parts)
        return module_name

    def parse_module(self, file_path, module_name):
        try:
            if file_path in self.module_cache:
                module = self.module_cache[file_path]
            else:
                module = self.builder.file_build(file_path, module_name)
                self.module_cache[file_path] = module
            return module
        except (AstroidError, FileNotFoundError, StopIteration) as e:
            self.logger.error(f"モジュール '{file_path}' の解析中にエラーが発生しました: {e}")
            return None

    def extract_definitions(self, module):
        for node in module.body:
            if isinstance(node, astroid.ClassDef):
                self._extract_class_definitions(node)
            elif isinstance(node, astroid.FunctionDef):
                qname = node.qname()
                func_def = {
                    "file_path": self.handler_module,
                    "class_name": None,
                    "function_name": node.name,
                    "qname": qname,
                    "node": node,
                }
                self.definitions.append(func_def)

    def _extract_class_definitions(self, class_node):
        qname = class_node.qname()
        class_def = {
            "file_path": self.handler_module,
            "class_name": class_node.name,
            "function_name": None,
            "qname": qname,
            "node": class_node,
        }
        self.definitions.append(class_def)

        # 明示的に定義されたメソッドのみを取得
        for method in class_node.mymethods():
            qname = method.qname()
            method_def = {
                "file_path": self.handler_module,
                "class_name": class_node.name,
                "function_name": method.name,
                "qname": qname,
                "node": method,
            }
            self.definitions.append(method_def)

        # 再帰的に内部クラスを処理
        for subclass in class_node.locals.values():
            for subnode in subclass:
                if isinstance(subnode, astroid.ClassDef):
                    self._extract_class_definitions(subnode)

    def find_references_in_file(self, file_path):
        absolute_file_path = os.path.join(self.project_path, file_path)
        module_name = self.get_module_qname(absolute_file_path)
        if not module_name:
            return

        module = self.parse_module(absolute_file_path, module_name)
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
