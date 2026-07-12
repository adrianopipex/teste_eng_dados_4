"""
Script de ETL - Etapa 1
Le o dataset de clientes sinteticos, aplica as regras de negocio solicitadas
e escreve nas camadas Bronze e Silver do Data Lake, registrando as
particoes no Glue Data Catalog.
"""

import re
from datetime import date

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, IntegerType, StringType, DateType, DoubleType
)
from pyspark.sql.window import Window


# ---------------------------------------------------------------------------
# Schema do dataset de origem
# ---------------------------------------------------------------------------
SCHEMA_CLIENTES = StructType([
    StructField("cod_cliente", IntegerType(), nullable=False),
    StructField("nm_cliente", StringType(), nullable=True),
    StructField("nm_pais_cliente", StringType(), nullable=True),
    StructField("nm_cidade_cliente", StringType(), nullable=True),
    StructField("nm_rua_cliente", StringType(), nullable=True),
    StructField("num_casa_cliente", IntegerType(), nullable=True),
    StructField("telefone_cliente", StringType(), nullable=True),
    StructField("dt_nascimento_cliente", DateType(), nullable=True),
    StructField("dt_atualizacao", DateType(), nullable=True),
    StructField("tp_pessoa", StringType(), nullable=True),
    StructField("vl_renda", DoubleType(), nullable=True),
])

BRONZE_PATH = "s3://bucket-bronze/tabela_cliente_landing"
SILVER_PATH = "s3://bucket-silver/tb_cliente"
BRONZE_TABLE = "db_bronze.tabela_cliente_landing"
SILVER_TABLE = "db_silver.tb_cliente"

PHONE_REGEX = r"^\(\d{2}\)\d{5}-\d{4}$"


def read_source(spark: SparkSession, input_path: str) -> DataFrame:
    """Le o CSV de origem aplicando o schema definido explicitamente."""
    return (
        spark.read
        .option("header", True)
        .option("sep", ",")
        .schema(SCHEMA_CLIENTES)
        .csv(input_path)
    )


def padronizar_nome(df: DataFrame) -> DataFrame:
    """Converte o nome do cliente para maiusculas."""
    return df.withColumn("nm_cliente", F.upper(F.col("nm_cliente")))


def renomear_coluna_telefone(df: DataFrame) -> DataFrame:
    """Renomeia telefone_cliente para num_telefone_cliente."""
    return df.withColumnRenamed("telefone_cliente", "num_telefone_cliente")


def adicionar_particao_processamento(df: DataFrame, data_processamento: date) -> DataFrame:
    """Adiciona a coluna anomesdia, usada como particao fisica e logica."""
    anomesdia = data_processamento.strftime("%Y%m%d")
    return df.withColumn("anomesdia", F.lit(anomesdia))


def escrever_bronze(df: DataFrame) -> None:
    """Escreve o dado bruto no bucket Bronze, particionado por anomesdia,
    e garante que a particao fique visivel no Glue Data Catalog."""
    (
        df.write
        .mode("append")
        .format("parquet")
        .partitionBy("anomesdia")
        .option("path", BRONZE_PATH)
        .insertInto(BRONZE_TABLE)  # a tabela ja existe no Glue Catalog
    )


def deduplicar_por_cliente(df: DataFrame) -> DataFrame:
    """Mantem apenas o registro mais recente (maior dt_atualizacao) de cada cliente."""
    janela = Window.partitionBy("cod_cliente").orderBy(F.col("dt_atualizacao").desc())
    return (
        df.withColumn("_rn", F.row_number().over(janela))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )


def validar_telefone(df: DataFrame) -> DataFrame:
    """Mantem apenas telefones no formato (NN)NNNNN-NNNN; os demais viram nulos."""
    return df.withColumn(
        "num_telefone_cliente",
        F.when(F.col("num_telefone_cliente").rlike(PHONE_REGEX), F.col("num_telefone_cliente"))
        .otherwise(F.lit(None).cast(StringType())),
    )


def escrever_silver(df: DataFrame) -> None:
    """Escreve o dado tratado no bucket Silver, particionado por anomesdia."""
    (
        df.write
        .mode("append")
        .format("parquet")
        .partitionBy("anomesdia")
        .option("path", SILVER_PATH)
        .insertInto(SILVER_TABLE)
    )


def main():
    spark = (
        SparkSession.builder
        .appName("etl_clientes")
        .enableHiveSupport()  # necessario para o Spark enxergar o Glue Data Catalog como metastore
        .getOrCreate()
    )

    data_processamento = date.today()
    input_path = "datasets/clientes_sinteticos.csv"

    df_raw = read_source(spark, input_path)

    df_bronze = (
        df_raw
        .transform(padronizar_nome)
        .transform(renomear_coluna_telefone)
        .transform(lambda d: adicionar_particao_processamento(d, data_processamento))
    )
    escrever_bronze(df_bronze)

    df_silver = (
        df_bronze
        .transform(deduplicar_por_cliente)
        .transform(validar_telefone)
    )
    escrever_silver(df_silver)

    spark.stop()


if __name__ == "__main__":
    main()