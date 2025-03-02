
import json 
import datetime 
import random
import mysql.connector
from mysql.connector import Error


def serialize_datetime(obj): 
    if isinstance(obj, datetime.datetime) or isinstance(obj, datetime.date): 
        return obj.isoformat() 
    raise TypeError("Type not serializable") 

def get_a_future_date():
    today = datetime.date.today()
    random_number = random.randint(1, 30)
    future_date = today + datetime.timedelta(days=random_number)

    return future_date


def create_db_connection(host_name, user_name, user_password, db_name):
    connection = None
    try:
        connection = mysql.connector.connect(
            host=host_name,
            user=user_name,
            passwd=user_password,
            database=db_name
        )
        print("MySQL Database connection successful")
    except Error as err:
        print(f"Error: '{err}'")

    return connection


def execute_query(connection, query):
    cursor = connection.cursor()
    try:
        cursor.execute(query)
        connection.commit()
        print("Query successful")
    except Error as err:
        print(f"Error: '{err}'")

def read_query(connection, query):
    cursor = connection.cursor(dictionary=True)
    result = None
    try:
        cursor.execute(query)
        result = cursor.fetchall()
        return result
    except Error as err:
        print(f"Error: '{err}'")

def get_acc_dict_by_acc_num(connection, account_number):
    query = f"""SELECT * FROM accountInformation WHERE account_number={account_number};"""
    results = read_query(connection, query)
    output_dict = results[0]
    for key,val in output_dict.items():
        if isinstance(val, datetime.date):
            val_str=val.strftime('%m/%d/%Y')
            output_dict[key]=val_str
    return output_dict

def get_credit_dict_by_acc_num(connection, account_number):
    query = f"""SELECT * FROM creditCard WHERE account_number={account_number};"""
    results = read_query(connection, query)
    output_dict = results[0]
    if output_dict['payment_due_date'] is not None:
        output_dict['payment_due_date'] = get_a_future_date()
    for key,val in output_dict.items():
        if isinstance(val, datetime.date):
            val_str=val.strftime('%m/%d/%Y')
            output_dict[key]=val_str
    return output_dict