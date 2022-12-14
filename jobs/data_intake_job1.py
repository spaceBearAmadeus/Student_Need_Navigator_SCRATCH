import json, os, re, sys
import logging 
from time import asctime 
from typing import Callable, Optional
from pyspark.sql.dataframe import DataFrame
from pyspark.sql import SparkSession
from pyspark.sql.functions import explode, col 
import seaborn as sns 
import matplotlib.pyplot as plt
import connectionDetails as cd 
import pandas as pd 

'''This script represents a series of jobs that the class will execute. These
jobs are particularly for the general trimming and standarizing of dtypes. This
has nothing to do with the preprocessing job script '''



#this is the FULL dir to the project, including nested folders, ending with THIS path
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#file path format for creating new logs...this project @whatever the name of the file is.log
LOG_FILE = f"{project_dir}/logs/job-{os.path.basename(__file__)}.log"
#the format of the actual log, with params specfied
LOG_FORMAT = f"%(asctime)s - LINE:%(lineno)d - %(name)s - %(levelname)s - %(funcName)s - %(message)s"
#creating a config for the logging based on our strings
logging.basicConfig(filename=LOG_FILE, level=logging.DEBUG, format=LOG_FORMAT)
#specifying the logger(jvm)
logger = logging.getLogger('log4j2')
#here we are allowing this path to be connected alongside classes
sys.path.insert(1, project_dir)

def define_pg_connection():
    def define_conn(dialect_and_driver, username, password, host, port, db_name):
        connection_string = f"{dialect_and_driver}://{username}:{password}@{host}:{port}/{db_name}"
        return connection_string

    pg_conn = define_conn(cd.conn_type, cd.username, cd.pwd, 
                          cd.hostname, cd.port_id, cd.db_name)
    return pg_conn 
   

from classes.spark_class import RoseSpark

def main_data_intake(project_dir:str) -> None:
    #this executes the func below, which requires the following formatted string(.json'''
    conf = open_config(f"{project_dir}/config/config.json")
    #this applies the string(config) to spark start
    rose = spark_start(conf)
    rose.conf.set("spark.sql.sources.commitProtocolClass", "org.apache.spark.sql.execution.datasources.SQLHadoopMapReduceCommitProtocol")
    rose.conf.set("parquet.enable.summary-metadata", "false")
    rose.conf.set("mapreduce.fileoutputcommitter.marksuccessfuljobs", "false")
    #create pg connection string
    connection = define_pg_connection()
    #use pd to read in sql table and convert to spark df!
    df = pd_to_spark_df(rose, "SELECT * FROM students_08142022", connection)
    #use job func to remove null and standardize schema
    clean_df = clean_student_data(rose, df) 
    #export the df into a csv that is in a dedicated dir...change file_name to specify new file_name
    export_clean_df(df=clean_df, project_dir=project_dir, file_name="cleaned_studentsU", is_spark=False)#<-filename to be written
    #clean_csv_name(project_dir, "cleaned_students")
    rose.stop()

 
def open_config(file_path: str) -> dict:
    if isinstance(file_path, str):
        return RoseSpark(config={}).open_file(file_path)

def spark_start(conf: dict) -> SparkSession:
    if isinstance(conf, dict):
        return RoseSpark(config={}).spark_start(conf)
    
def spark_stop(spark:SparkSession) -> None:
    spark.stop() if isinstance(spark, SparkSession) else None 

#read in df with sql and pandas and then convert to spark df(get around jdbc issue)   
def pd_to_spark_df(spark, sql, conn):
    df1 = pd.read_sql(sql, con=conn)
    df2 = spark.createDataFrame(df1)
    return df2

#here we have a function that cleans null and casts correct dtypes with spark
def clean_student_data(spark, df):
  #replace null values in different cols with spark
  def replace_null(spark, df) -> DataFrame:
    df.createOrReplaceTempView("d1")
    df1 = spark.sql("SELECT *, CASE WHEN contact_info IS NULL OR contact_info = 'NaN' THEN 'contact thru store' else contact_info end as contact FROM d1;")
    df2 = df1.drop(col("contact_info"))
    df2.createOrReplaceTempView("d2")
    df3 = spark.sql("select *, case when lesson_time like 'NULL' OR lesson_time = 'NaN' then 440 else lesson_time end as time from d2")
    df4 = df3.drop(col("lesson_time"))
    df4.createOrReplaceTempView("d3")
    df5 = spark.sql("select *, case when day_of_study IS NULL OR day_of_study = 'NaN' then 'Thursday' else day_of_study end as lesson_day from d3")\
              .drop(col("day_of_study"))
    df5.createOrReplaceTempView("d4")
    df6 = spark.sql("select *, case when age like 'NULL' OR age = 'NaN' then 14.6 else age end as student_age from d4")\
              .drop(col("age"))
    return df6
    
  def standardize_schema(df):
    #standardize dtypes in schema and then drop copys of columns 
    df0 = df.select("*")\
            .withColumn("date_started", col("date_entered").cast("Date"))\
            .withColumn("time_of_lesson", col("time").cast("Double"))\
            .withColumn("age", col("student_age").cast("Double"))\
            .drop(col("student_age")).drop(col("time")).drop(col("date_entered"))
    return df0

  df_first = replace_null(spark, df)
  df_final = standardize_schema(df_first)
  print("final df schema:\n")
  df_final.printSchema()
  print("final df\n")
  df_final.show()
  return df_final 

#takes the same amount of args
def export_clean_df(df:DataFrame, project_dir:str, file_name:str, is_spark:bool):
    if isinstance(df, DataFrame):
        return RoseSpark(config={}).clean_df_to_csv(df, project_dir, file_name, is_spark)
    
def clean_csv_name(project_dir, file_name):
    return RoseSpark(config={}).clean_file_names(project_dir, file_name)
    
#if __name__ == "__main__":
#    main_data_intake(project_dir)


#export to dedicated dir for sending to another db as a table that will 
    #soon have the model's predictions appended on to it!  




