
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

def make_payment(user_payment_fields,user_account_fields,payment_mode='FULL'):
    if payment_mode=='FULL':
        amount_to_be_paid = user_payment_fields["amount_due"]
    elif payment_mode=='MIN':
        amount_to_be_paid = user_payment_fields["minimum_amount_due"] 
    user_payment_fields["is_payment_due"] = 'F'
    user_payment_fields["payment_due_date"] = None
    user_payment_fields["amount_due"] = None
    user_payment_fields["minimum_amount_due"] = None
    user_account_fields["account_balance"] -= amount_to_be_paid

    return user_payment_fields,user_account_fields

def update_address(user_account_fields,house_number=None,street_name=None,zip_code=None):
    user_account_fields["zip_code"] = zip_code
    user_account_fields["address"] = str(house_number) + " " + street_name

    return user_account_fields