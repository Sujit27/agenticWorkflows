
import json 
import datetime 
import random
import mysql.connector
from mysql.connector import Error
import pandas as pd


def load_data_files(*args):
    df_list = []
    for file_name in args:
        df = pd.read_csv(file_name)
        df_list.append(df)

    return df_list

def get_a_future_date():
    today = datetime.date.today()
    random_number = random.randint(1, 30)
    future_date = today + datetime.timedelta(days=random_number)

    return future_date


def get_user_info_by_acc(df,account_number):
    try:
        output_dict = df[df['account_number']==account_number].to_dict(orient='records')[0]
        if 'payment_due_date' in output_dict:
            output_dict['payment_due_date'] = get_a_future_date()

        return output_dict
    except:
        print(f"Account number {account_number} not found !")
        return None