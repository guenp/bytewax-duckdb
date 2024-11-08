import os
import sys
from pathlib import Path
from typing import List, Optional

if "BYTEWAX_LICENSE" not in os.environ:
    msg = (
        "`bytewax-duckdb` is commercially licensed "
        "with publicly available source code.\n"
        "You are welcome to prototype using this module for free, "
        "but any use on business data requires a paid license.\n"
        "See https://modules.bytewax.io/ for a license. "
        "Set the env var `BYTEWAX_LICENSE=1` to suppress this message."
    )
    print(msg, file=sys.stderr)

import pyarrow as pa  # type: ignore
import duckdb as md_duckdb
from bytewax.operators import V
from bytewax.outputs import FixedPartitionedSink, StatefulSinkPartition


class DuckDBSinkPartition(StatefulSinkPartition[V, None]):
    """Stateful sink partition for writing data to either local DuckDB or MotherDuck."""

    def __init__(
        self,
        db_path: str,
        table_name: str,
        create_table_sql: Optional[str],
        resume_state: None,
    ) -> None:
        """Initialize the DuckDB or MotherDuck connection, and create tables if needed.

        Args:
            db_path (str): Path to the DuckDB database file or MotherDuck connection string.
            table_name (str): Name of the table to write data into.
            create_table_sql (Optional[str]): SQL statement to create the table if
                the table does not already exist.
            resume_state (None): Unused, as this sink does not perform recovery.
        """
        self.table_name = table_name
        self.conn = md_duckdb.connect(db_path)

        # Only create the table if specified and if it doesn't already exist
        if create_table_sql:
            self.conn.execute(create_table_sql)

    def write_batch(self, batches: List[V]) -> None:
        """Write a batch of items to the DuckDB or MotherDuck table.

        Args:
            batches (List[V]): List of batches of items to write.
        """
        for batch in batches:
            pa_table = pa.Table.from_pylist(batch)

            # Insert data into the target table
            self.conn.register("temp_table", pa_table)
            self.conn.execute(f"INSERT INTO {self.table_name} SELECT * FROM temp_table")
            self.conn.unregister("temp_table")

    def snapshot(self) -> None:
        """This sink does not support recovery."""
        return None

    def close(self) -> None:
        """Close the DuckDB or MotherDuck connection."""
        self.conn.close()


class DuckDBSink(FixedPartitionedSink):
    """Fixed partitioned sink for writing data to DuckDB or MotherDuck.

    This sink writes to a single output DB, optionally creating
    it with a create table SQL statement when first invoked.
    """

    def __init__(
        self,
        db_path: str,
        table_name: str = "default_table",
        create_table_sql: Optional[str] = None,
    ) -> None:
        """Initialize the DuckDBSink.

        Args:
            db_path (str): DuckDB database file path or MotherDuck connection string.
            table_name (str): Name of the table to write data into.
            create_table_sql (Optional[str]): SQL statement to create the table
                if it does not already exist.
        """
        self.db_path = db_path
        self.table_name = table_name
        self.create_table_sql = create_table_sql

    def list_parts(self) -> List[str]:
        """Returns a single partition to write to.

        Returns:
            List[str]: List of a single partition key.
        """
        return ["partition_0"]

    def build_part(
        self,
        step_id: str,
        for_part: str,
        resume_state: None,
    ) -> DuckDBSinkPartition:
        """Build or resume a partition.

        Args:
            step_id (str): The step ID.
            for_part (str): Partition key.
            resume_state (None): Resume state.

        Returns:
            DuckDBSinkPartition: The partition instance.
        """
        return DuckDBSinkPartition(
            db_path=self.db_path,
            table_name=self.table_name,
            create_table_sql=self.create_table_sql,
            resume_state=resume_state,
        )
