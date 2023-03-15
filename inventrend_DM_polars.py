# %% Load Modules
from pickle import TRUE
from datetime import datetime, date, timedelta
from dateutil.relativedelta import *
import time
from calendar import month
import pandas as pd
import numpy as np
import pyodbc
# import smartsheet
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

import polars as pl
# %%
timelist = []

start = time.time()

username = 'kiradba'
password = 'Kiss!234!'
server = '10.1.3.25'
database = 'KIRA'
trusted_conn = 'no'

conn = f'mssql://{username}:{password}@{server}/{database}?driver=SQL+Server&trusted_connection={trusted_conn}'

connection_string = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=' + \
    server+';DATABASE='+database+';UID='+username+';PWD=' + password
connection_url = URL.create(
    "mssql+pyodbc", query={"odbc_connect": connection_string})
engine = create_engine(connection_url, fast_executemany=True)
print("Connection Established:")


end = time.time()
timelist.append([end-start, "Connect to KIRA server"])
# %%
# query_mtrl=f'''( SELECT material FROM [ivy.mm.dim.fact_poasn] WHERE act_date >=getdate() GROUP BY material )
# UNION
# (SELECT material from [ivy.mm.dim.mrp01] WHERE total_stock>0 GROUP BY material)
# ORDER BY material'''

# # df_mtrl= pl.read_sql(query_mtrl,conn)
# df_mtrl.head()

# %%%

df_past = pd.read_sql("""
DECLARE @pastNmth as int = 6;
SELECT T2.material,  T2.plant, act_date, cost_amt as total_value, qty as total_stock  FROM [ivy.sd.fact.inven] T2
WHERE act_date > DATEADD(M,-@pastNmth , getdate())
and plant in ('1100','1110','1400','1410','G140')
""", con=engine, parse_dates=["act_date"])

# df_past=pl.from_pandas(df_past)
df_past.head()

# %%
df_current = pd.read_sql("""
    SELECT T2.material, pl_plant as plant, total_value, 
    CASE WHEN total_stock = 0 THEN T3.mtrlcost ELSE total_value/ cast(total_stock as float) END as mtrlcost, 
    total_stock,
    CONVERT(varchar(10),T2.cur_date, 101) as act_date
    FROM [ivy.mm.dim.mrp01] T2 
    LEFT JOIN [ivy.mm.dim.mtrl] T3 on T2.material = T3.material
    WHERE pl_plant in ('1100','1110','1400','1410','G140')
""", con=engine, parse_dates=["act_date"])
df_current=df_current.sort_values(
    by=['material', 'plant', 'act_date']).reset_index().drop('index', axis=1)

# df_current=pl.from_pandas(df_current)
df_current.head()

# %%
df_demand = pd.read_sql("""
DECLARE @pastNmth as int = 6, @futureNmth as int = 15;
DECLARE @current_date date = getdate();
DECLARE @TheFirstOfMonth as date = (SELECT TheFirstOfMonth FROM [ivy.mm.dim.date] where Thedate =  CAST(getdate() as date)); 
DECLARE @TheLastOfMonth as date = (SELECT TheLastOfMonth FROM [ivy.mm.dim.date] where Thedate =  CAST(getdate() as date)) ;
DECLARE @TheFirstfutuerNmth as date = ( SELECT FORMAT(dateadd(M, @futureNmth, dateadd(DD,-DAY(getdate())+1,getdate()))    ,'yyyy-MM-dd') );
DECLARE @TheFirstpastNmth as date = ( dateadd(M,-@pastNmth,dateadd(DD,-DAY(   getdate())+1,   getdate())  ) );

WITH fcstT2 as (
    SELECT T1.material,plant, act_date,aship, eship
    -- CASE WHEN act_date =(SELECT TheFirstOfMonth FROM [ivy.mm.dim.date] where Thedate = @current_date )
    -- THEN eship*CAST(Tdate.workdaysLeftInMonth as float)/ CAST( Tdate.workdaysInMonth as float )
    --     ELSE eship END as eship
    FROM [ivy.mm.dim.factfcst] T1
    LEFT JOIN [ivy.mm.dim.date] Tdate on Tdate.thedate= T1.act_date
    WHERE act_date>=@TheFirstOfMonth
    and act_date <=@TheFirstfutuerNmth
    and plant in ('1100', '1110', '1400', '1410','G140')
)
,ppp as (
    SELECT T1.material, T1.plant,avg( cast (T1.qty as float) ) as qty, 
    T4.TheFirstOfMonth as act_date 
    FROM [ivy.sd.fact.bill_ppp] T1
    LEFT JOIN [ivy.mm.dim.date] T4 on T1.act_date = T4.Thedate
    WHERE T1.act_date >=  @TheFirstpastNmth
    and T1.plant in ('1100', '1110', '1400', '1410','G140')    
    GROUP BY T1.material, T4.TheFirstOfMonth, T1.plant
), ppp2 as (
    SELECT material, plant, CASE when qty <0 then 0 else qty END as qty, act_date from ppp
), Tdate AS (
    SELECT TheDate as act_date FROM [ivy.mm.dim.date]
    WHERE TheDate BETWEEN @TheFirstOfMonth and @TheFirstfutuerNmth
    and TheDate= TheFirstOfMonth
), Tplant as (
    SELECT plant
    FROM (VALUES ('1100'), ('1110'), ('1400'), ('1410'), ('G140')) AS tbl(plant)
), Tmtrl as (
    SELECT material
    FROM ppp2
    UNION
    SELECT material
    FROM fcstT2
)
    SELECT Tmtrl.material, Tplant.plant, Tdate.act_date, COALESCE(T1.eship, T2.qty) as demand_qty
    FROM  Tmtrl  
    CROSS JOIN Tplant
    CROSS JOIN Tdate
    LEFT JOIN fcstT2 T1 on Tdate.act_date= T1.act_date and Tplant.plant=T1.plant and Tmtrl.material= T1.material
    LEFT JOIN ppp2 T2 on Tplant.plant=T2.plant and Tmtrl.material= T2.material
""", con=engine, parse_dates=["act_date"])
# df_demand=pl.from_pandas(df_demand)
df_demand = df_demand.sort_values(
    by=['material', 'plant', 'act_date']).reset_index().drop('index', axis=1)
df_demand.head()

# %%

df_mtrl = pd.read_sql("""( SELECT material FROM [ivy.mm.dim.fact_poasn] WHERE act_date >=getdate() GROUP BY material )
UNION 
(SELECT material from [ivy.mm.dim.mrp01] WHERE total_stock>0 GROUP BY material)
ORDER BY material""", con=engine
                      )
# df_mtrl= pl.from_pandas(df_mtrl)
df_mtrl.head()

# %%
df_date = pd.read_sql("""SELECT * FROM [ivy.mm.dim.date]
WHERE year(THEDATE) > YEAR(getdate())-2 and year(TheDate) < YEAR(getdate())+2
""", con=engine)
# df_date= pl.from_pandas(df_date)
df_date.head()

end = time.time()
timelist.append([end-start, "Get full table from SQL server"])

print("Get full table from SQL server")
# %%

# Load planned order data if it exists
try:
    df_poasn = pd.read_sql(
        "SELECT * FROM [ivy.mm.dim.fact_poasn]", con=engine, parse_dates=["act_date"])
    po_exist = True
except:
    po_exist = False

# %%
# Create new DataFrame for projected inventory
projected_inventory_data = []

import calendar

material='KPEG06'

# Iterate over each material
for material in df_material["material"].unique():
    current_data = df_current[df_current["material"] == material]
    demand_data = df_demand[df_demand ["material"]== material]
    poasn_data =df_poasn[df_poasn["material"]==material]
    
    start_date = current_data.iloc[-1]["act_date"]   
    # monthly loop should be added
    act_date = current_data.iloc[-1]["act_date"]
    
    Theyear= act_date.year
    Themonth= act_date.month
    first_day_month = datetime(Theyear, Themonth, 1)
    last_day_month = datetime(Theyear, Themonth, calendar.monthrange(Theyear,Themonth)[1])

    mask = poasn_data["act_date"].between(act_date,last_day_month)
    if sum(mask)>0:
        poasn_data_selected=poasn_data[mask]
        bo_date, po_date, po_qty = find_backorder(
            df_demand, current_data, material, start_date)
        if bo_qty > 0:
            projected_inventory_data.append(
                {"material": material, "act_date": po_date - pd.Timedelta(days=1), "qty": 0})
            projected_inventory_data.append(
                {"material": material, "act_date": po_date, "qty": po_qty})
        else:
            last_qty = current_data["total_stock"].iloc[-1] if not current_data.empty else 0
            total_demand = df_demand[df_demand["material"]
                                     == material]["qty"].sum()
        if last_qty - total_demand >= 0:
            projected_inventory_data.append({"material": material, "act_date": start_date.replace(
                day=start_date.days_in_month), "qty": last_qty - total_demand})
        else:
            business_days = np.busday_count(
                start_date.date(), start_date.replace(day=start_date.days_in_month).date())
            bo_date = start_date.replace(day=start_date.days_in_month) + pd.Timedelta(
                days=int(last_qty * business_days / total_demand))
            po_date, po_qty = find_next_planned_order(
                df_planned_orders, material, bo_date)
        if po_date is None:
            projected_inventory_data.append(
                {"material": material, "act_date": bo_date, "qty": 0})
        else:
            projected_inventory_data.append(
                {"material": material, "act_date": po_date - pd.Timedelta(days=1), "qty": 0})
            projected_inventory_data.append(
                {"material": material, "act_date": po_date, "qty": po_qty})
#            Convert projected inventory data to DataFrame
            projected_inventory = pd.DataFrame(projected_inventory_data)
#            Merge projected inventory with current inventory and planned orders data if they exist
        if not df_current.empty:
            projected_inventory = projected_inventory.merge(
                df_current[["material", "act_date", "total_stock"]], on=["material", "act_date"], how="left")
        if po_exist:
            projected_inventory = projected_inventory.merge(
                df_planned_orders, on=["material", "act_date"], how="left")
#        Save projected inventory to CSV file
        projected_inventory.to_csv("projected_inventory.csv", index=False)


# # %%
# start = time.time()
# df_trend["DM"]=0
# df_trend["Demand"]=0

# mtrl_colnames = df_mtrl.columns   # Index(['material'], dtype='object')
# trend_colnames = df_trend.columns # ['material', 'act_date', 'totalstock', 'totalvalue', 'mtrlcost','label','DM','Demand'],
# demand_colnames = df_demand.columns     #['material', 'act_date', 'qty']

# df_mtrl = df_mtrl.to_numpy()
# df_trend= df_trend.to_numpy()
# df_demand= df_demand.to_numpy()

# # for index0, row0 in df_mtrl.iterrows():
# for index_mtrl in range(len(df_mtrl)):
#     print(df_mtrl[index_mtrl,0])
#     # print( f'{df_mtrl.loc[index_mtrl][0]:15} {float(index_mtrl+1)/float(len(df_mtrl))*100:.2f}% ') # print % progress

#     # trend=df_trend.loc[df_trend["material"]==row0.material,["material","act_date","totalstock"]]
#     trend=df_trend[df_trend[:,0]==df_mtrl[index_mtrl,0],0:3]
#     # demand=df_demand.loc[df_demand["material"]==row0.material]
#     demand=df_demand[df_demand[:,0]==df_mtrl[index_mtrl,0]]
#     # for index, row in trend.iterrows():
#     for index_date in range(len(trend)):

#         if len(demand)==0:
#             df_trend[(df_trend[:,0]==trend[0,0]) &(df_trend[:,1]==trend[index_date,1]),6]=999
#             df_trend[(df_trend[:,0]==trend[0,0]) &(df_trend[:,1]==trend[index_date,1]),7]=0
#         else:
#             # demandIn=demand.loc[demand["act_date"] > row.act_date ].copy()
#             demandIn=demand[demand[:,1]>trend[index_date,1]]
#             # cumsumQty=demandIn["qty"].cumsum()
#             # demandIn.loc[:,"cumsum"]=cumsumQty
#             cumsumQty=demandIn[:,2].cumsum()
#             demandIn=np.append(demandIn, cumsumQty[:,np.newaxis],axis=1)

#             # demandIn2=demandIn.loc[row.totalstock-demandIn["cumsum"]<0].head(1)
#             demandIn2=demandIn[trend[index_date,2]-demandIn[:,3]<0]
#             if len(demandIn2)>0:
#                 demandIn2=demandIn2[0]

#                 if trend[index_date,2]==0:
#                     DM=0
#                     # df_trend.loc[(df_trend["material"]==row.material) &(df_trend["act_date"]==row.act_date),"demand"]=0
#                     df_trend[(df_trend[:,0]==demandIn2[0]) &(df_trend[:,1]==trend[index_date,1]),7]=0
#                 else:
#                     # qty=demandIn2["qty"].values[0]
#                     qty=demandIn2[2]
#                     # deltaMonth=relativedelta.relativedelta(demandIn2["act_date"].values[0],row.act_date).months
#                     deltaMonth=relativedelta.relativedelta(demandIn2[1],trend[index_date,1]).months
#                     # DM=deltaMonth-1+(row.totalstock)/qty
#                     DM=(deltaMonth-1)+(trend[index_date,2])/qty
#                     # df_trend.loc[(df_trend["material"]==row.material) &(df_trend["act_date"]==row.act_date),"demand"]=row.totalstock/DM
#                     df_trend[(df_trend[:,0]==demandIn2[0]) &(df_trend[:,1]==trend[index_date,1]),7]=trend[index_date,2]/DM
#             else:
#                 DM=999
#                 # df_trend.loc[(df_trend["material"]==row.material) &(df_trend["act_date"]==row.act_date),"demand"]=0
#                 df_trend[(df_trend[:,0]==demand[0,0]) &(df_trend[:,1]==trend[index_date,1]),7]=0

#             # df_trend.loc[(df_trend["material"]==row.material) &(df_trend["act_date"]==row.act_date),"DM"]=DM
#             df_trend[(df_trend[:,0]==demand[0,0]) &(df_trend[:,1]==trend[index_date,1]),6]=DM

# end = time.time()
# timelist.append([end-start, "DM and demand calc"])
# # %%

# df_trend=pd.DataFrame(df_trend)
# df_trend.columns = trend_colnames
# file_loc = r'C:\Users\KISS Admin\Desktop\IVYENT_DH\P8. Inventory Monitoring Report'
# # total_loc = file_loc+"\\"+today+"_"+targetPlant+"_ESA.csv"
# total_loc = file_loc+"\\"+"_trend.csv"

# df_trend.to_csv(total_loc)
# print('csv')


# # %%
# df_time = pd.DataFrame(timelist)
# df_time.columns = ["time", "desc"]
# df_time["ratio"] = df_time["time"].apply(
#     lambda x: f'{(x/sum(df_time["time"])*100):.2f}')
# df_time.sort_values("time", ascending=False, inplace=True)
# # df_time["time"]=df_time["time"].apply(lambda x : f'{x:.2f}')
# df_time = df_time[["desc", "time", "ratio"]]
# print(df_time)
# # %%
# %%


# %%
