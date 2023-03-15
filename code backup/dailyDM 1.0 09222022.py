# %%
import pandas as pd
import numpy as np
from pandas._libs.tslibs import NaT
from pandas.core.arrays.sparse import dtype
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
import datetime
import time
# %%
start = time.time()
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
# get forecast table
time2 = time.time()
print(f"{time2-start:.4f}sec")


# %%
print("start to read full table")
df_ft = pd.read_sql("""WITH ppp --avgMreorder within 3month, material, plant FROM [dbo].[bill_ppp]
AS (
    SELECT ROUND(SUM(CONVERT(FLOAT, qty)) / 3, 3) AS avgMreorder, material, plant
    FROM ppp_temp
    WHERE act_date BETWEEN DATEADD(MM, - 3, DATEADD(DD, - DAY(GETDATE()), GETDATE()))
            AND DATEADD(DD, - DAY(GETDATE()), GETDATE())
        AND ordsqc > 1
    GROUP BY material, plant
    ), backOrder	-- avgMbo within 3month, material, plant FROM [ivy.sd.fact.bo] 
AS (
    SELECT SUM(CONVERT(FLOAT, bo_qty)) / 3 AS avgMbo, material, plant
    FROM [ivy.sd.fact.bo]
    WHERE (
            act_date BETWEEN DATEADD(MM, - 3, DATEADD(DD, - DAY(GETDATE()), GETDATE()))
                AND DATEADD(DD, - DAY(GETDATE()), GETDATE())
            )
    GROUP BY material, plant
    ), T4fcst -- Table to make fcst table. FROM this month to upcoming 5 month
AS (
    SELECT material, eship, FORMAT(act_date, 'MMyyyy') AS MMYYYY, plant
    FROM [ivy.mm.dim.factfcst]
    WHERE act_date BETWEEN GETDATE()
                AND DATEADD(MONTH, 6, GETDATE())
    ), T4fcst2 -- 	GROUP BY material, MMYYYY, plant
AS (
    SELECT material, SUM(eship) AS eship, MMYYYY, plant
    FROM T4fcst
    GROUP BY material, MMYYYY, plant
        --ORDER BY material, plant, MMYYYY
    ), fcst -- Date, WorkingDates in That month, MMYYYY, fcstPerWorkingDates, plant, material
AS (
    SELECT T1.TheDate, T1.WorkingDates, T1.MMYYYY, T1.IsWeekend, CONVERT(FLOAT, T2.eship) / CONVERT(FLOAT, T1.WorkingDates) AS fcstPerWorkingDates, T2.plant, T2.material
    FROM (
        SELECT TheDate, COUNT(*) OVER (PARTITION BY MMYYYY) AS WorkingDates, MMYYYY, IsWeekend
        FROM [ivy.mm.dim.date]
        WHERE isweekend != 1
            AND thedate BETWEEN GETDATE()
                AND DATEADD(MONTH, 6, GETDATE())
        ) T1
    LEFT JOIN T4fcst2 T2 ON T1.MMYYYY = T2.MMYYYY
    ), Tpoasn as (
    SELECT material, plant, act_date, sum(po_qty) as po_qty, sum(asn_qty) as asn_qty
    FROM [ivy.mm.dim.fact_poasn]
    GROUP BY material, plant, act_date
    ), TOTAL AS (
    SELECT 	T2.PL_plant, T1.thedate, T3.material, T1.IsWeekend, CONVERT(FLOAT, T4.avgMbo) / CONVERT(FLOAT, T9.WorkingDates) AS avgDbo, T5.po_qty + T5.asn_qty AS poasn_qty, T6.avgMreorder, CONVERT(FLOAT, T6.avgMreorder) / CONVERT(FLOAT, T9.WorkingDates) AS avgDreorder, T8.total_stock - T8.blocked - T8.subcont_qty AS On_hand_qty, T9.fcstPerWorkingDates
    FROM (
        SELECT DISTINCT PL_PLANT -- pl_plant
        FROM [ivy.mm.dim.mrp01]
        ) T2
    CROSS JOIN (
        SELECT THEDATE, IsWeekend -- thedate
        FROM [ivy.mm.dim.date]
        WHERE thedate BETWEEN GETDATE()
                AND DATEADD(MONTH, 6, GETDATE())
        ) T1
    CROSS JOIN (
        SELECT MATERIAL --material
        FROM [ivy.mm.dim.mtrl]
        WHERE DIVISION in ('N3') AND--
         MS = '01'
        ) T3
    LEFT JOIN backOrder T4 ON T3.material = T4.material -- avgDailybo
        AND T2.pl_plant = T4.plant
    LEFT JOIN Tpoasn T5 ON T3.material = T5.material -- poasn_qty
        AND T2.pl_plant = T5.plant
        AND T1.TheDate = T5.act_date
    LEFT JOIN ppp T6 ON T3.material = T6.material -- average Monthly reorder qty
        AND T2.pl_plant = T6.plant
    LEFT JOIN [ivy.mm.dim.mrp01] T8 ON T3.material = T8.material -- on_hand qty
        AND T2.pl_plant = T8.pl_plant
    LEFT JOIN fcst T9 ON T3.material = T9.material -- fcstPerWorkingDates, isWeekend
        AND T2.pl_plant = T9.plant
        AND T9.TheDate = T1.TheDate
        ), TOTAL2 -- NULL value to 0 (avgDbo, poasn_qty, avgDreorder, fcstPerworkingDates,On_hand_qty)
AS (
    SELECT pl_plant, TheDate, material, CASE 
            WHEN (avgDbo IS NULL)
                THEN 0
            ELSE avgDbo
            END AS avgDbo, CASE 
            WHEN (poasn_qty IS NULL)
                THEN 0
            ELSE poasn_qty
            END AS poasn_qty, CASE 
            WHEN (avgDreorder IS NULL)
                THEN 0
            ELSE avgDreorder
            END AS avgDreorder, CASE 
            WHEN (fcstPerWorkingDates IS NULL)
                THEN 0
            ELSE fcstPerWorkingDates
            END AS fcstPerWorkingDates, CASE 
            WHEN (On_hand_qty IS NULL)
                THEN 0
            ELSE On_hand_qty
            END AS On_hand_qty,
            IsWeekend
    FROM Total
    )
    SELECT pl_plant as plant, TheDate, material as mtrl, avgDbo, poasn_qty, avgDreorder, On_hand_qty, 
    CASE WHEN (fcstPerWorkingDates=0 and IsWeekend=0) THEN avgDreorder+avgDbo else fcstPerWorkingDates END AS fcstD,
    avgDbo+avgDreorder as demandD
    FROM TOTAL2
""", con=engine)
time1 = time.time()
print(f"{time1-start:.4f}sec")
time.sleep(1)
#df_fcst = pd.read_sql("""SELECT a.Material, a.Plant, a.act_date, a.qty FROM [KIRA].[dbo].[ivy.mm.dim.factfcst_all] a LEFT JOIN [KIRA].[dbo].[ivy.mm.dim.mtrl] b ON a.Material = b.material WHERE b.ms in ('03', '07', '01') AND b.mg  NOT IN ('PP', 'X1') AND a.act_date = (select format(getdate(),'yyyy-MM-01')) AND b.material NOT LIKE '%%TTSET%%' AND b.material NOT LIKE '%%TESTERSET%%';""", con=engine)
# %%
#
# TODO : df_mtrl, df_date dependent to change using df_ft.mtrl and df_ft.TheDate
df_mtrl = pd.read_sql("""SELECT MATERIAL as mtrl
        FROM [ivy.mm.dim.mtrl]
        WHERE DIVISION in ('N3') AND-- -- ('N3','C1','L6','E4')--
        MS = '01' """, con=engine)

df_date = pd.read_sql("""SELECT THEDATE
        FROM [ivy.mm.dim.date]
        WHERE thedate BETWEEN GETDATE()
                AND DATEADD(MONTH, 6, GETDATE())""", con=engine)
# %%

df = df_ft.groupby(["mtrl", "TheDate"]).sum()
df = df.reset_index()

df["BOseq"] = 999
df["residue"] = 999
# %%
for index_mtrl in range(len(df_mtrl)):
    print(df_mtrl.loc[index_mtrl].to_string())
    BOflag = 0
    curBOseq = 0
    curResidue = df.loc[index_mtrl*len(df_date), "On_hand_qty"]
    poasn_test = df.loc[df["mtrl"] == df.loc[index_mtrl *
                                             len(df_date), "mtrl"], "poasn_qty"].sum() == 0
    if(curResidue == 0 & poasn_test):
        df.loc[index_mtrl*len(df_date):(index_mtrl+1) *
               len(df_date)-1, "residue"] = 0
        df.loc[index_mtrl*len(df_date):(index_mtrl+1) *
               len(df_date)-1, "BOseq"] = 1
    else:
        for index_date in range(len(df_date)):
            curIndex = index_mtrl*len(df_date)+index_date
            if BOflag == 1:
                if df.loc[curIndex, "poasn_qty"] > 0:
                    BOflag = 0
                    df.loc[curIndex, "BOseq"] = 0
                    curResidue = curResidue + \
                        df.loc[curIndex, "poasn_qty"]-df.loc[curIndex, "fcstD"]
                df.loc[curIndex, "BOseq"] = curBOseq
            else:
                curResidue = curResidue + \
                    df.loc[curIndex, "poasn_qty"]-df.loc[curIndex, "fcstD"]
                if curResidue <= 0:
                    curBOseq += 1
                    curResidue = 0
                    BOflag = 1
                    df.loc[curIndex, "BOseq"] = curBOseq
                else:
                    df.loc[curIndex, "BOseq"] = 0
            df.loc[curIndex, "residue"] = curResidue
# %%
print("creating The result table was done")
time2 = time.time()
print(f"{time2-start:.4f}sec")
# %%
print(df)
df.to_csv('TotalDailyDM.csv')
df.to_csv(r'Y:\OM ONLY_Shared Documents\5 Reports with Power Query\Source Data\PyCodes\dailyDM\TotalDailyDM.csv')

# %%
print('exporting TotalDailyDM.csv was done')

df_result = df.groupby(['mtrl', 'BOseq']).agg(
    {'TheDate': ['min', 'count', 'max']})
df_result = df_result.reset_index()
df_result.to_csv('TotalBOresults.csv')
df_result.to_csv(
    r'Y:\OM ONLY_Shared Documents\5 Reports with Power Query\Source Data\PyCodes\dailyDM\TotalBOresults.csv')

print('end')
# %%
time3 = time.time()

print(f"{time3-start:.4f}sec")
