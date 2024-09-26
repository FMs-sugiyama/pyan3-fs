# specification

- 指定されたPythonプロジェクトパス(project_path}の指定されたモジュール(target_module}配下にある全てのソースコードを解析します
- 指定されたfastapiのhandlerスクリプト(handler_module}から、@api.get/post/put/deleteなどのデコレータで指定されたエンドポイントの情報を取得します
- そのエンドポイントを起点として、ソースコードの呼び出し階層を解析します
- 呼び出し階層の結果は、result.csvファイルに、以下のカラムを持つCSVファイルとして出力します
  - endpoint: 起点となったエンドポイントのパス
  - method: 起点となったエンドポイントのHTTPメソッド
  - module_name: 呼び出された処理のモジュール名
  - class_name: 呼び出された処理のクラス名（クラスのmethodの場合。なければnull）
  - function_name: 呼び出された処理の関数名
  - depth: エンドポイントからの呼び出し階層の深さ

# constraints

- jediを利用すること
- jedi.Projectで指定されたモジュール内の全てのソースコードを解析対象とすること
- subprocessは利用しないこと
- astモジュールは極力直接は使用しないこと（ライブラリ等からの間接的な利用は問題ない）
- 循環参照が発生した呼び出し階層はその時点で再帰呼び出しを打ち切って良い
- project_path/target_module/handler_moduleは定数で指定できること

# class name

- CodeAnalyzer