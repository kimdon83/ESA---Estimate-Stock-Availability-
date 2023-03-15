# %%
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from pandas._libs.tslibs import NaT
from pandas.core.arrays.sparse import dtype
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from datetime import datetime
from dateutil.relativedelta import *
import time
import matplotlib.pyplot as plt
import matplotlib as mpl

server = '10.1.3.25'
database = 'KIRA'
username = 'kiradba'
password = 'Kiss!234!'
connection_string = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=' + \
    server+';DATABASE='+database+';UID='+username+';PWD=' + password
connection_url = URL.create(
    "mssql+pyodbc", query={"odbc_connect": connection_string})
engine = create_engine(connection_url, fast_executemany=True)
print("Connection Established:")


# %%
df_mrp = pd.read_sql("""
SELECT material, pl_plant,dlv_plant, pdt FROM [ivy.mm.dim.mrp01] ORDER BY material
""", con=engine)

df_mtrl = pd.read_sql("""
SELECT material, dlv_plant, pdt FROM [ivy.mm.dim.mtrl] ORDER BY material
""", con=engine)


# %%
df=df_mrp.merge(df_mtrl, on='material')
# %%
df[df['pdt_x']==df['pdt_y']]
# %%
