import astroid
import os
import sys
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
    ):
        """
        初期化メソッド

        Args:
            project_path (str): プロジェクトのルートディレクトリのパス
            handler_module (str): 解析対象のモジュールの相対パス（プロジェクトルートから）
            scan_module (str, optional): スキャン対象のサブモジュールまたはディレクトリの相対パス（プロジェクトルートから）
            max_workers (int): 並列処理のスレッド数
        """
        self.project_path = os.path.abspath(project_path)
        self.handler_module = handler_module
        self.handler_module_path = os.path.join(self.project_path, self.handler_module)
        self.scan_module = scan_module  # スキャン対象モジュールの追加
        self.max_workers = max_workers

        print(f"Handler module path: {self.handler_module_path}")

        if not os.path.isfile(self.handler_module_path):
            print(f"Error: Handler module '{self.handler_module_path}' does not exist.")
            sys.exit(1)

        # プロジェクトパスを sys.path に追加して、astroid が正しくモジュール名を推論できるようにする
        if self.project_path not in sys.path:
            sys.path.insert(0, self.project_path)

        # astroid Builder のインスタンスを作成
        self.builder = AstroidBuilder()

    def get_module_qname(self, file_path):
        """
        ファイルパスからモジュールの完全修飾名（QNAME）を取得する関数

        Args:
            file_path (str): ファイルの絶対パス

        Returns:
            str: モジュールの完全修飾名
        """
        try:
            relative_path = Path(file_path).relative_to(self.project_path)
        except ValueError:
            print(
                f"Error: File '{file_path}' is not under project path '{self.project_path}'."
            )
            return None

        # プロジェクトパスがトップレベルのパッケージディレクトリであることを前提としています
        # 例: project_path = /path/to/project, file_path = /path/to/project/clubjt_impl/api/user/service/address.py
        # → module_name = clubjt_impl.api.user.service.address
        parts = relative_path.with_suffix("").parts
        module_name = ".".join(parts)
        print(f"Derived module name for '{file_path}': {module_name}")
        return module_name

    def find_references_in_file(self, file_path: str, def_qnames: set):
        """
        指定されたファイル内での参照を検索する関数

        Args:
            file_path (str): 解析対象のファイルのパス
            def_qnames (set): 定義の完全修飾名のセット

        Returns:
            list: 見つかった参照のリスト
        """
        references = []
        try:
            module_name = self.get_module_qname(file_path)
            if not module_name:
                return references
            # AstroidBuilder.file_build() を使用してモジュールをビルド
            module = self.builder.file_build(file_path, module_name)
        except (AstroidError, FileNotFoundError) as e:
            print(f"Error parsing file '{file_path}': {e}")
            return references

        # Nameノードと Attributeノードを取得
        name_nodes = module.nodes_of_class(astroid.Name)
        attribute_nodes = module.nodes_of_class(astroid.Attribute)

        # Nameノードの参照をチェック
        for node in name_nodes:
            try:
                inferred_defs = node.infer()
            except InferenceError:
                # InferenceErrorは無視
                continue
            except Exception as e:
                print(
                    f"Unexpected error during inference for node '{node.name}' in '{file_path}': {e}"
                )
                continue

            for inferred_def in inferred_defs:
                inferred_qname = inferred_def.qname()
                if inferred_qname:
                    # builtins.* をスキップ
                    if inferred_qname.startswith("builtins."):
                        continue
                    print(
                        f"Checking Name node '{node.name}' in '{file_path}': inferred_qname = '{inferred_qname}'"
                    )
                    if inferred_qname in def_qnames:
                        references.append(
                            {
                                "name": node.name,
                                "file": file_path,
                                "line": node.lineno,
                                "column": node.col_offset,
                            }
                        )
                        print(
                            f"Reference found: {node.name} in {file_path} at {node.lineno}:{node.col_offset}"
                        )

        # Attributeノードの参照をチェック
        for node in attribute_nodes:
            try:
                inferred_defs = node.infer()
            except InferenceError:
                # InferenceErrorは無視
                continue
            except Exception as e:
                print(
                    f"Unexpected error during inference for node '{node.attrname}' in '{file_path}': {e}"
                )
                continue

            for inferred_def in inferred_defs:
                inferred_qname = inferred_def.qname()
                if inferred_qname:
                    # builtins.* をスキップ
                    if inferred_qname.startswith("builtins."):
                        continue
                    print(
                        f"Checking Attribute node '{node.attrname}' in '{file_path}': inferred_qname = '{inferred_qname}'"
                    )
                    if inferred_qname in def_qnames:
                        full_name = inferred_qname
                        references.append(
                            {
                                "name": full_name,
                                "file": file_path,
                                "line": node.lineno,
                                "column": node.col_offset,
                            }
                        )
                        print(
                            f"Reference found: {full_name} in {file_path} at {node.lineno}:{node.col_offset}"
                        )

        return references

    def run(self):
        """
        参照を検索し、結果を表示するメソッド
        """
        try:
            # ハンドラーモジュールをビルド
            module_a_qname = self.get_module_qname(self.handler_module_path)
            if not module_a_qname:
                print(
                    f"Error: Could not derive module name for '{self.handler_module_path}'."
                )
                sys.exit(1)
            module_a = self.builder.file_build(self.handler_module_path, module_a_qname)
            print("Parsing succeeded.")
            print(f"module_a qname: {module_a.qname()}")
            print(f"module_a type: {type(module_a)}")
            print(f"module_a attributes: {dir(module_a)}")
        except (AstroidError, FileNotFoundError) as e:
            print(f"Error parsing module '{self.handler_module_path}': {e}")
            sys.exit(1)

        # モジュール内の全てのクラス、関数、メソッドを取得
        try:
            definitions = []
            for node in module_a.body:
                if isinstance(node, astroid.ClassDef):
                    definitions.append(node)
                    # クラスのメソッドも定義に追加
                    methods = list(node.methods())
                    definitions.extend(methods)
                elif isinstance(node, astroid.FunctionDef):
                    definitions.append(node)
            print(f"Found {len(definitions)} classes/functions/methods.")
            print("Definitions:")
            for defn in definitions:
                print(f" - {defn.qname()} ({defn.__class__.__name__})")
        except AttributeError as e:
            print(f"Error accessing classes or functions: {e}")
            print(f"module_a type: {type(module_a)}")
            print(f"module_a attributes: {dir(module_a)}")
            sys.exit(1)

        if not definitions:
            print(f"No classes or functions found in '{self.handler_module_path}'.")
            return

        # 定義の完全修飾名のセットを作成（builtins.* を除外）
        def_qnames = set()
        for defn in definitions:
            qname = defn.qname()
            if qname and not qname.startswith("builtins."):
                def_qnames.add(qname)
                print(f"Definition QNAME: {qname}")

        # プロジェクト内の全ファイルを取得
        if self.scan_module:
            # scan_module が指定されている場合、そのサブモジュール内のファイルのみをスキャン対象とする
            scan_path = os.path.join(self.project_path, self.scan_module)
            if not os.path.isdir(scan_path):
                print(
                    f"Error: Scan module '{self.scan_module}' does not exist under project path."
                )
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
            # scan_module が指定されていない場合、プロジェクト全体をスキャン対象とする
            py_files = [
                os.path.join(root, file)
                for root, dirs, files in os.walk(self.project_path)
                for file in files
                if file.endswith(".py")
                and os.path.abspath(os.path.join(root, file))
                != os.path.abspath(self.handler_module_path)
            ]

        print(f"Scanning {len(py_files)} Python files for references...")

        references = []

        # 並列処理で参照を検索
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {
                executor.submit(
                    self.find_references_in_file, file_path, def_qnames
                ): file_path
                for file_path in py_files
            }
            for future in as_completed(future_to_file):
                try:
                    file_refs = future.result()
                    references.extend(file_refs)
                except Exception as e:
                    file_path = future_to_file[future]
                    print(f"Error processing file '{file_path}': {e}")

        # 結果を表示
        if references:
            print(f"\nReferences to definitions in '{self.handler_module}' found:")
            for ref in references:
                print(
                    f" - {ref['name']} is referenced in {ref['file']} at line {ref['line']}, column {ref['column']}"
                )
        else:
            print(
                f"\nNo references to definitions in '{self.handler_module}' were found."
            )


if __name__ == "__main__":
    # プロジェクトのルートディレクトリを設定（'clubjt_impl' の親ディレクトリ）
    PROJECT_PATH = "/Users/sugiyama/clubjt-server/clubjt-impl"
    HANDLER_MODULE = "clubjt_impl/api/user/service/address.py"  # モジュールの相対パス
    SCAN_MODULE = "clubjt_impl"  # スキャン対象のサブモジュールまたはディレクトリの相対パス（例: 'clubjt_impl'）

    # FileParserのインスタンスを作成して実行
    parser = FileParser(
        project_path=PROJECT_PATH,
        handler_module=HANDLER_MODULE,
        scan_module=SCAN_MODULE,  # スキャン対象モジュールの指定
        max_workers=8,
    )
    parser.run()
