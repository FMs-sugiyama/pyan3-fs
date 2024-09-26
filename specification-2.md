# specification

- 指定されたPythonプロジェクトパス(project_path}の指定されたモジュール(target_module}配下にある全てのソースコードを解析します
- 指定されたpythonファイルのfunctionもしくはclass methodをリストアップします。これを仮に「エンドポイント」と呼びます
- そのエンドポイントを参照する他のファイルのfunctionもしくはclass methodをリストアップします。
- 結果は、result.csvファイルに、以下のカラムを持つCSVファイルとして出力します
  - endpoint/file_path
  - endpoint/module_name
  - endpoint/class_name（module functionならnull）
  - endpoint/function_name
  - referer/file_path
  - referer/module_name
  - referer/class_name（module functionならnull）
  - referer/function_name

# constraints

- jedi = "^0.19.1"を利用すること。これより若いバージョンとのハルシネーションに十分注意して出力を行うこと
- jedi.Projectで指定されたモジュール内の全てのソースコードを解析対象とすること
- subprocessは利用しないこと
- astモジュールは極力直接は使用しないこと（ライブラリ等からの間接的な利用は問題ない）
- 循環参照が発生した呼び出し階層はその時点で再帰呼び出しを打ち切って良い
- project_path/target_module/handler_moduleは定数で指定できること

# class name

- CodeAnalyzer