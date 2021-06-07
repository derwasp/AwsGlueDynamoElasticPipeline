import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from pyspark.sql.functions import col, udf
from pyspark.sql.types import StringType

import requests

## @prams: [JOB_NAME]
args = getResolvedOptions(sys.argv, ['JOB_NAME','dynamo_table_name','es_endpoint'])

dynamo_table = args['dynamo_table_name']

es_endpoint = args['es_endpoint']
es_index = 'somedata'

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

def indexExists(elastic_endpoint, index_name):
    if elastic_endpoint.endswith('/'):
        elastic_endpoint = elastic_endpoint[:-1]
    url = elastic_endpoint + '/' + index_name
    response = requests.head(url)
    return response.ok == True

def createIndex(elastic_endpoint, index_name, mappings):
    if elastic_endpoint.endswith('/'):
        elastic_endpoint = elastic_endpoint[:-1]
    url = elastic_endpoint + '/' + index_name
    response = requests.put(url, json = mappings)
    return response.ok == True

dynamoDataSource = glueContext.create_dynamic_frame.from_options(
            connection_type = "dynamodb",
            connection_options = { "dynamodb.input.tableName" : dynamo_table, "dynamodb.throughput.read.percent" : "1" })

if not indexExists(es_endpoint, es_index):
    print("Creating index: ", es_index)
    mappings = {
            "mappings": {
                "properties": {
                    "prop1": {
                        "type": "keyword"
                    },
                    "prop2": {
                        "type": "keyword"
                    }
                    "prop3": {
                        "type": "text"
                    }
                    "prop4": {
                        "type": "date"
                    }
                }
            }
        }
    creationResult = createIndex(es_endpoint, es_index, mappings)
    print("Creation result: ", creationResult)

columns_to_drop = ['PK', 'SK']

df = dynamoDataSource.toDF()

my_df = df.filter(df.SK.startswith('AwesomePrefix#'))

my_df = my_df.drop(*columns_to_drop)

my_df.write.mode("overwrite").format("org.elasticsearch.spark.sql").\
        option("es.resource", "index/type").\
        option("es.nodes", es_endpoint).\
        option("es.port", 443).\
        option("es.nodes.wan.only", True).\
        option("es.index.auto.create", False).\
        option("es.resource", es_index).\
        option("es.mapping.id", "id").\
        option("es.write.operation", "upsert").\
        save()
print("Moved records: ", my_df.count())

print("Total records: ", df.count())

job.commit()
