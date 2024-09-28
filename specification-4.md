以下の要件を満たす完全で実行可能なPythonコードを生成してください：

1. astroidを使用してPythonコードの静的解析を行う、ClubjtErrorAnalyzerという名前のクラスを実装してください。

2. 主な機能：
   - PROJECT_PATHで指定されたPythonプロジェクトの、TARGET_MODULE配下の全ての.pyファイルを走査します。
   - 指定された例外クラス（ClubjtError, ClubjtModuleError, ClubjtAuth0Error, ClubjtAuth0AuthenticationAPIError, ClubjtAuth0ManagementAPIError）をraiseする箇所を見つけます。
   - 見つかった各raiseステートメントについて、以下の情報を抽出します：
     a) 発生元情報：file_path（PROJECT_PATHからの相対パス）, class_name（クラスメソッドの場合、そうでなければNull）, function_name
     b) 発生エラー情報：error_class_name, status_code, reason, message
   - 抽出した情報をCSVファイル（clubjt_error_result.csv）に出力します。

3. 実装詳細：
   - executeメソッドを実装し、このメソッドから解析を開始します。
   - f-stringを含む複雑な文字列も適切に処理できるようにします。
   - エラーのコンストラクタ引数は、キーワード引数または位置引数（1:status_code, 2:reason, 3:message）として処理します。
   - messageが指定されていない場合、デフォルト値としてCOMMON_ERROR_MESSAGEを使用します。

4. 定数：
   - PROJECT_PATH = "/Users/sugiyama/clubjt-server/clubjt-impl"
   - TARGET_MODULE = "clubjt_impl"
   - COMMON_ERROR_MESSAGE = "ただいま混み合っております。 誠に申し訳ございませんが、しばらくしてからもう一度やり直してください。"

5. コーディング規約：
   - Python 3.10以上と互換性のあるコードを記述してください。
   - 関数とメソッドに明確な型アノテーションを使用し、組み込み型のみを使用してください（typingモジュールは使用しない）。
   - PEP 8スタイルガイドラインに準拠してください。
   - 綿密なエラー処理とログ記録を実装してください。
   - 静的メソッドの代わりに@classmethodデコレータを使用してください。

6. コードは__main__から実行されるようにしてください。

省略のない、完全で実行可能なPythonコードファイルを生成してください。非現実的または機能しないソリューションは避けてください。