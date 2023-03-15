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

server = '10.1.3.25' 
database = 'KIRA' 
username = 'kiradba'                                                                                                                                                                                                                  
password = 'Kiss!234!' 
connection_string = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER='+server+';DATABASE='+database+';UID='+username+';PWD='+ password
connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
engine = create_engine(connection_url)
print("Connection Established:")

# todays = datetime.today()
# first_days = todays.replace(day=1)
# last_days = datetime(todays.year, todays.month, 1) + relativedelta(months=1) + relativedelta(seconds=-1)
# days_left = last_days - todays
# today = todays.strftime('%Y-%m-%d')
# first_day = first_days.strftime('%Y-%m-%d')
# last_day = last_days.strftime('%Y-%m-%d')
# business_days = np.busday_count(begindates=first_day, enddates=today) #By today
# business_days_thismonth = np.busday_count(begindates=first_day, enddates=last_day)
# business_days_left = np.busday_count(begindates=today, enddates=last_day) 
end = time.time()
timelist.append([end-start, "Connect to KIRA server"])
# %%
start = time.time()

# orderlimit_df = pd.read_sql("""SELECT material, from_date, to_date FROM [ivy.mm.dim.orderlimit] WHERE from_date<=GETDATE() and to_date>=GETDATE()""", con=engine)
df_trend = pd.read_sql("""DECLARE @pastNmth as int = 6, @futureNmth as int = 7;
-- SELECT @pastNmth as aa, @futureNmth

-- change act_date from first date of the month to last date of the month in fcst and poasn at cumsumfcst and cumsumpoasn. eg) 3/1 -> 3/31
-- inventoryTrend is union of past, projT3, mrpT with material, plant, act_date, totalvalue, label

WITH mtrlT as (
( SELECT material FROM [ivy.mm.dim.fact_poasn] WHERE act_date >=getdate() and plant in ('1100','1110','1400','1410') GROUP BY material )
UNION 
(SELECT material from [ivy.mm.dim.mrp01] WHERE total_stock>0 and pl_plant in ('1100','1110','1400','1410') GROUP BY material)
), dateT as (
    SELECT TheLastOfMonth as act_date FROM [ivy.mm.dim.date]
    WHERE Thedate>=DATEADD(M,-@pastNmth , getdate()) and TheDate<=dateadd(M, @futureNmth, dateadd(DD,-DAY(getdate())+1,getdate())) 
    GROUP BY TheLastOfMonth
)
, mtrlDate as (
    SELECT * FROM mtrlT
    CROSS JOIN dateT
), past as (
    SELECT T2.material,  T2.plant, act_date, cost_amt, qty  FROM [ivy.sd.fact.inven] T2
    WHERE act_date > DATEADD(M,-@pastNmth , getdate())
    and plant in ('1100','1110','1400','1410')
), poasnT1 as (
    SELECT material, T2.TheLastOfMonth as act_date, sum(po_qty+ asn_qty) as poasn_qty,plant 
    FROM [ivy.mm.dim.fact_poasn] T1
    LEFT JOIN [ivy.mm.dim.date] T2 on T1.act_date=T2.TheDate
    WHERE act_date>=GETDATE() and plant in ('1100', '1100', '1400', '1410')
    GROUP BY T2.TheLastOfMonth, material, plant
), cumsumpoasn as ( 
    SELECT material, plant, act_date, 
    sum(poasn_qty) OVER (PARTITION BY material, plant order by act_date ROWS between UNBOUNDED PRECEDING AND CURRENT ROW) as cumsumQty FROM poasnT1
), fcstT1 AS (
    SELECT T1.* FROM [ivy.mm.dim.factfcst] T1
    WHERE act_date>=(SELECT TheFirstOfMonth FROM [ivy.mm.dim.date] where Thedate = CAST(getdate() as date))
    and act_date <=FORMAT(dateadd(M, @futureNmth, dateadd(DD,-DAY(getdate())+1,getdate()))    ,'yyyy-MM-dd')
    and plant in ('1100', '1110', '1400', '1410')
),fcst as (
    SELECT material,plant, aship, TheLastOfMonth as act_date
    ,CASE WHEN act_date =Tdate.TheFirstOfMonth
    THEN eship*CAST(Tdate.workdaysLeftInMonth as float)/ CAST( Tdate.workdaysInMonth as float )
        ELSE eship END as eship
    FROM [ivy.mm.dim.factfcst] T1
    LEFT JOIN [ivy.mm.dim.date] Tdate on Tdate.thedate= T1.act_date
), cumsumfcst as (
    SELECT material, plant, act_date, 
    sum(eship) OVER (PARTITION BY material, plant order by act_date ROWS between UNBOUNDED PRECEDING AND CURRENT ROW) as cumsumQty FROM fcst
), mrpT as (
    SELECT T1.material, pl_plant as plant, total_value, 
    CASE WHEN total_stock = 0 THEN T3.mtrlcost ELSE total_value/ cast(total_stock as float) END as mtrlcost, 
    FORMAT(dateadd(DD,-1,T2.cur_date),'yyyy-MM-dd') as act_date, total_stock
    FROM mtrlT T1
    LEFT JOIN [ivy.mm.dim.mrp01] T2 on T1.material = T2.material
    LEFT JOIN [ivy.mm.dim.mtrl] T3 on T1.material = T3.material
    WHERE pl_plant in ('1100','1110','1400','1410') 
), projT as (
    (SELECT material, plant, total_value, mtrlcost, total_stock, (SELECT TheLastOfMonth FROM [ivy.mm.dim.date] where Thedate = CAST(getdate() as date)) as act_date FROM mrpT)
    union 
    (SELECT material, plant, total_value, mtrlcost, total_stock, (SELECT TheLastOfMonth FROM [ivy.mm.dim.date] where Thedate = CAST(DATEADD(M,1,getdate()) as date)) as act_date FROM mrpT)
    union 
    (SELECT material, plant, total_value, mtrlcost, total_stock, (SELECT TheLastOfMonth FROM [ivy.mm.dim.date] where Thedate = CAST(DATEADD(M,2,getdate()) as date)) as act_date FROM mrpT)
    union 
    (SELECT material, plant, total_value, mtrlcost, total_stock, (SELECT TheLastOfMonth FROM [ivy.mm.dim.date] where Thedate = CAST(DATEADD(M,3,getdate()) as date)) as act_date FROM mrpT)
    union 
    (SELECT material, plant, total_value, mtrlcost, total_stock, (SELECT TheLastOfMonth FROM [ivy.mm.dim.date] where Thedate = CAST(DATEADD(M,4,getdate()) as date)) as act_date FROM mrpT)
    union 
    (SELECT material, plant, total_value, mtrlcost, total_stock, (SELECT TheLastOfMonth FROM [ivy.mm.dim.date] where Thedate = CAST(DATEADD(M,5,getdate()) as date)) as act_date FROM mrpT)
    union 
    (SELECT material, plant, total_value, mtrlcost, total_stock, (SELECT TheLastOfMonth FROM [ivy.mm.dim.date] where Thedate = CAST(DATEADD(M,@futureNmth-1,getdate()) as date)) as act_date FROM mrpT)
), projT2 as (
    SELECT T1.material, T1.plant, T1.act_date,
    total_value- COALESCE(  cast(T2.cumsumQty as float),0)  *T1.mtrlcost +  coalesce(cast (T3.cumsumQty as float ),0)   *T1.mtrlcost as totalvalue,
    total_stock- COALESCE(  cast(T2.cumsumQty as float),0)    +  coalesce(cast (T3.cumsumQty as float ),0)     as totalstock, mtrlcost
      FROM projT T1
    LEFT JOIN cumsumfcst T2 on T1.material= T2.material and T1.plant = T2.plant and T1.act_date = T2.act_date
    LEFT JOIN cumsumpoasn T3 on T1.material= T3.material and T1.plant = T3.plant and T1.act_date = T3.act_date
), projT3 as (
    SELECT material, plant, act_date, 
    CASE WHEN totalvalue>0 THEN totalvalue ELSE 0 END totalvalue,
    CASE WHEN totalstock>0 THEN totalstock ELSE 0 END totalstock, mtrlcost
     FROM projT2
), inventoryTrend as (
    (SELECT *, 'proj' as label FROM projT3 )
    union all
    (SELECT material, plant, act_date, total_value, total_stock, mtrlcost, 'current' as label FROM mrpT)
    union all
    (SELECT material, plant, act_date, cost_amt, qty, cost_amt/ cast( qty as float) as mtrlcost , 'past' as label FROM past )
), inventoryTrend2 as (
SELECT material, act_date, SUM(totalvalue) as totalvalue, sum(totalstock) as totalstock, AVG(mtrlcost) as mtrlcost, label FROM inventoryTrend
GROUP BY material, act_date, label
)
SELECT T1.material, T1.act_date, totalstock,totalvalue,  mtrlcost, label FROM mtrlDate T1
LEFT JOIN inventoryTrend2 T2 on T1.material=T2.material and T1.act_date = T2.act_date
WHERE label is not null
ORDER BY  T1.material, T1.act_date
""", con=engine)
df_trend.head()

# %%
# df_demand.to_csv("demandDATA.csv", index=False)
# df_demand=pd.read_csv("demandDATA.csv", parse_dates=["act_date"])

# df_demand["act_date"]=df_demand["act_date"].dt.to_pydatetime()

df_demand = pd.read_sql("""
DECLARE @pastNmth as int = 6, @futureNmth as int = 15;
DECLARE @current_date date = getdate();
DECLARE @TheFirstOfMonth as date = (SELECT TheFirstOfMonth FROM [ivy.mm.dim.date] where Thedate =  CAST(getdate() as date)); 
DECLARE @TheLastOfMonth as date = (SELECT TheLastOfMonth FROM [ivy.mm.dim.date] where Thedate =  CAST(getdate() as date)) ;
DECLARE @TheFirstfutuerNmth as date = ( SELECT FORMAT(dateadd(M, @futureNmth, dateadd(DD,-DAY(getdate())+1,getdate()))    ,'yyyy-MM-dd') );
DECLARE @TheFirstpastNmth as date = ( dateadd(M,-@pastNmth,dateadd(DD,-DAY(   getdate())+1,   getdate())  ) );

-- Materialize subquery into temporary table
SELECT T1.material,plant, act_date,aship,
    CASE WHEN act_date = @TheFirstOfMonth
    THEN eship*CAST(Tdate.workdaysLeftInMonth as float)/ CAST( Tdate.workdaysInMonth as float )
        ELSE eship END as eship
INTO #fcstT2
FROM [ivy.mm.dim.factfcst] T1
LEFT JOIN [ivy.mm.dim.date] Tdate on Tdate.thedate= T1.act_date
LEFT JOIN [ivy.mm.dim.mrp01] T3 on T1.material=T3.material and T1.plant= T3.pl_plant
LEFT JOIN [ivy.mm.dim.mtrl] T4 on T1.material= T4.material
WHERE act_date>=@TheFirstOfMonth
and act_date <=@TheFirstfutuerNmth
and plant in ('1100', '1110', '1400', '1410')

-- Add appropriate indexes to the tables used in the query

-- Use a derived table instead of a CTE
SELECT material, act_date, sum(eship) as qty
INTO #fcstT3
FROM #fcstT2
GROUP BY material, act_date

-- Use a derived table instead of a CTE
SELECT T1.material, T1.plant, sum(T1.qty) as qty, 
    T4.TheFirstOfMonth as act_date 
INTO #ppp
FROM [ivy.sd.fact.bill_ppp] T1
LEFT JOIN [ivy.sd.fact.inven] T2 on T1.material = T2.material and T1.plant = T2.plant
LEFT JOIN [ivy.mm.dim.mtrl] T3 on T1.material = T3.material
LEFT JOIN [ivy.mm.dim.date] T4 on T1.act_date = T4.Thedate
WHERE T1.act_date >= @TheFirstpastNmth
and T3.material is not null
and T1.plant in ('1100', '1110', '1400', '1410')
GROUP BY T1.material, T4.TheFirstOfMonth, T1.plant

-- Use a derived table instead of a CTE
SELECT material, sum(qty) as qty, act_date
INTO #ppp2
FROM #ppp T1
GROUP BY T1.material, act_date

-- Combine the two tables into a single result set
SELECT material, T2.TheLastOfMonth as act_date,
sum(qty) as qty
FROM (
SELECT material, act_date, qty FROM #ppp2
UNION ALL
SELECT material, act_date, qty FROM #fcstT3
) AS demand
LEFT JOIN [ivy.mm.dim.date] T2 on demand.act_date = T2.TheDate
GROUP BY material, T2.TheLastOfMonth
ORDER BY material, act_date

-- Drop the temporary tables
DROP TABLE #fcstT2
DROP TABLE #fcstT3
DROP TABLE #ppp
DROP TABLE #ppp2

""", con=engine)
df_demand.head()

# %%

df_mtrl= pd.read_sql("""( SELECT material FROM [ivy.mm.dim.fact_poasn] WHERE act_date >=getdate() GROUP BY material )
UNION 
(SELECT material from [ivy.mm.dim.mrp01] WHERE total_stock>0 GROUP BY material)
ORDER BY material""", con=engine
)
df_mtrl.head()

# %%
df_date= pd.read_sql("""SELECT * FROM [ivy.mm.dim.date]
WHERE year(THEDATE) > YEAR(getdate())-2 and year(TheDate) < YEAR(getdate())+2
""", con=engine)
df_date.head()
end = time.time()
timelist.append([end-start, "Get full table from SQL server"])

print("Get full table from SQL server")

# %%
start = time.time()
df_trend["DM"]=0
df_trend["Demand"]=0

mtrl_colnames = df_mtrl.columns   # Index(['material'], dtype='object')
trend_colnames = df_trend.columns # ['material', 'act_date', 'totalstock', 'totalvalue', 'mtrlcost','label','DM','Demand'],
demand_colnames = df_demand.columns     #['material', 'act_date', 'qty']

df_mtrl = df_mtrl.to_numpy()
df_trend= df_trend.to_numpy()
df_demand= df_demand.to_numpy()

# for index0, row0 in df_mtrl.iterrows():
for index_mtrl in range(len(df_mtrl)):
    print(df_mtrl[index_mtrl,0])
    # print( f'{df_mtrl.loc[index_mtrl][0]:15} {float(index_mtrl+1)/float(len(df_mtrl))*100:.2f}% ') # print % progress

    # trend=df_trend.loc[df_trend["material"]==row0.material,["material","act_date","totalstock"]]
    trend=df_trend[df_trend[:,0]==df_mtrl[index_mtrl,0],0:3]
    # demand=df_demand.loc[df_demand["material"]==row0.material]
    demand=df_demand[df_demand[:,0]==df_mtrl[index_mtrl,0]]
    # for index, row in trend.iterrows():
    for index_date in range(len(trend)):

        if len(demand)==0:
            df_trend[(df_trend[:,0]==trend[0,0]) &(df_trend[:,1]==trend[index_date,1]),6]=999
            df_trend[(df_trend[:,0]==trend[0,0]) &(df_trend[:,1]==trend[index_date,1]),7]=0
        else:
            # demandIn=demand.loc[demand["act_date"] > row.act_date ].copy()
            demandIn=demand[demand[:,1]>trend[index_date,1]]
            # cumsumQty=demandIn["qty"].cumsum()
            # demandIn.loc[:,"cumsum"]=cumsumQty
            cumsumQty=demandIn[:,2].cumsum()
            demandIn=np.append(demandIn, cumsumQty[:,np.newaxis],axis=1)
            
            # demandIn2=demandIn.loc[row.totalstock-demandIn["cumsum"]<0].head(1)
            demandIn2=demandIn[trend[index_date,2]-demandIn[:,3]<0]
            if len(demandIn2)>0:
                demandIn2=demandIn2[0]

                if trend[index_date,2]==0:
                    DM=0
                    # df_trend.loc[(df_trend["material"]==row.material) &(df_trend["act_date"]==row.act_date),"demand"]=0    
                    df_trend[(df_trend[:,0]==demandIn2[0]) &(df_trend[:,1]==trend[index_date,1]),7]=0    
                else:
                    # qty=demandIn2["qty"].values[0]
                    qty=demandIn2[2]
                    # deltaMonth=relativedelta.relativedelta(demandIn2["act_date"].values[0],row.act_date).months
                    deltaMonth=relativedelta.relativedelta(demandIn2[1],trend[index_date,1]).months
                    # DM=deltaMonth-1+(row.totalstock)/qty
                    DM=(deltaMonth-1)+(trend[index_date,2])/qty
                    # df_trend.loc[(df_trend["material"]==row.material) &(df_trend["act_date"]==row.act_date),"demand"]=row.totalstock/DM 
                    df_trend[(df_trend[:,0]==demandIn2[0]) &(df_trend[:,1]==trend[index_date,1]),7]=trend[index_date,2]/DM 
            else:
                DM=999
                # df_trend.loc[(df_trend["material"]==row.material) &(df_trend["act_date"]==row.act_date),"demand"]=0    
                df_trend[(df_trend[:,0]==demand[0,0]) &(df_trend[:,1]==trend[index_date,1]),7]=0    
                
            # df_trend.loc[(df_trend["material"]==row.material) &(df_trend["act_date"]==row.act_date),"DM"]=DM          
            df_trend[(df_trend[:,0]==demand[0,0]) &(df_trend[:,1]==trend[index_date,1]),6]=DM          

end = time.time()
timelist.append([end-start, "DM and demand calc"])        
# %%

df_trend=pd.DataFrame(df_trend)
df_trend.columns = trend_colnames
file_loc = r'C:\Users\KISS Admin\Desktop\IVYENT_DH\P8. Inventory Monitoring Report'
# total_loc = file_loc+"\\"+today+"_"+targetPlant+"_ESA.csv"
total_loc = file_loc+"\\"+"_trend.csv"

df_trend.to_csv(total_loc)
print('csv')



# %%
df_time = pd.DataFrame(timelist)
df_time.columns = ["time", "desc"]
df_time["ratio"] = df_time["time"].apply(
    lambda x: f'{(x/sum(df_time["time"])*100):.2f}')
df_time.sort_values("time", ascending=False, inplace=True)
# df_time["time"]=df_time["time"].apply(lambda x : f'{x:.2f}')
df_time = df_time[["desc", "time", "ratio"]]
print(df_time)
# %%
