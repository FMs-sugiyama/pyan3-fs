import duckdb
from pydantic import BaseModel


class FastApiEndpoint(BaseModel):
    module_name: str
    http_method: str
    path: str
    operation_id: str


class FastApiEndpointDatasource:
    def __init__(self, csv_path: str = "fastapi_endpoints.csv"):
        self.csv_path = csv_path
        self.conn = None

    def __enter__(self):
        self.conn = duckdb.connect(database=":memory:", read_only=False)
        self._load_csv()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def _load_csv(self):
        self.conn.execute(
            f"""
            CREATE TABLE endpoints AS 
            SELECT * FROM read_csv_auto('{self.csv_path}')
        """
        )

    def get_endpoints(
        self, handler: str | None = None, operation_id: str | None = None
    ) -> list[FastApiEndpoint]:
        query = "SELECT * FROM endpoints"
        conditions = []

        if handler:
            conditions.append(f"module_name = '{handler}'")
        if operation_id:
            conditions.append(f"operation_id = '{operation_id}'")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        result = self.conn.execute(query).fetchall()
        return [
            FastApiEndpoint(
                module_name=row[0], http_method=row[1], path=row[2], operation_id=row[3]
            )
            for row in result
        ]


# Sample usage
if __name__ == "__main__":
    with FastApiEndpointDatasource() as datasource:
        # Get all endpoints
        all_endpoints = datasource.get_endpoints()
        print("All endpoints:")
        for endpoint in all_endpoints:
            print(endpoint)

        # Get endpoints for a specific handler
        user_endpoints = datasource.get_endpoints(handler="user_handler")
        print("\nUser handler endpoints:")
        for endpoint in user_endpoints:
            print(endpoint)

        # Get a specific endpoint by operation_id
        specific_endpoint = datasource.get_endpoints(operation_id="get_my_last_name")
        print("\nSpecific endpoint:")
        for endpoint in specific_endpoint:
            print(endpoint)

    # No need to explicitly call close() - it's handled automatically
