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


# %%
timelist = []

# %%
targetPlant='total'
print(f'target plant:{targetPlant}')
todays = datetime.today()
# first_days = todays.replace(day=1)
# last_days = datetime(todays.year, todays.month, 1) + relativedelta(months=1) + relativedelta(seconds=-1)
# days_left = last_days - todays
today = todays.strftime('%Y-%m-%d')
curYM = todays.strftime('%Y%m')
# first_day = first_days.strftime('%Y-%m-%d')
# last_day = last_days.strftime('%Y-%m-%d')
# business_days = np.busday_count(begindates=first_day, enddates=today) #By today
# business_days_thismonth = np.busday_count(begindates=first_day, enddates=last_day)
# business_days_left = np.busday_count(begindates=today, enddates=last_day)
# %%
# Connect to KIRA server
start = time.time()
import json

with open('data.json', 'r') as f:
    data = json.load(f)

# ID와 비밀번호 가져오기
server = data['server']
database = data['database']
username = data['username']
password = data['password']

connection_string = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=' + \
    server+';DATABASE='+database+';UID='+username+';PWD=' + password
connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
engine = create_engine(connection_url, fast_executemany=True)
print("Connection Established:")

end = time.time()
timelist.append([end-start, "Connect to KIRA server"])
# %%
# choose the calculation type 1. whole plant, 2. individual plant 3. stock check
# calType= input("choose the calculation type 1. whole material 2. stock check ")
# %%
# get the full table for this calcutation.
start = time.time()

print("start to read full table")
df_ft = pd.read_sql("""
DECLARE @mthwitdh AS INT
SELECT @mthwitdh = 7;

WITH Tdate
AS (
    SELECT COUNT(*) AS WDs
    FROM [ivy.mm.dim.date]
    WHERE isweekend != 1 AND thedate BETWEEN DATEADD(MM, - 3, DATEADD(DD, - 1, GETDATE())) AND DATEADD(DD, - 1, 
                    GETDATE())
    GROUP BY IsWeekend
    ), pppDailyThisMonth
AS (
    SELECT SUM(qty) AS thisMthReOdqty, material, plant
    FROM [ivy.sd.fact.bill_ppp]
    WHERE act_date BETWEEN DATEADD(DD, 1, EOMONTH(GETDATE(), - 1)) AND GETDATE() AND ordsqc > 1
    GROUP BY material, plant
    ), ppp
    --avgMreorder within 3month, material, plant FROM [ivy.sd.fact.bill_ppp]
AS (
    SELECT SUM(qty) AS reorder3M, material, plant
    FROM [ivy.sd.fact.bill_ppp]
    WHERE act_date BETWEEN DATEADD(MM, - 3, DATEADD(DD, - 1, GETDATE())) AND DATEADD(DD, - 1, GETDATE()) AND ordsqc > 
        1
    GROUP BY material, plant
    ), backOrder
    -- avgMbo within 3month, material, plant FROM [ivy.sd.fact.bo] 
AS (
    SELECT SUM(bo_qty) AS bo3M, material, plant
    FROM [ivy.sd.fact.bo]
    WHERE (act_date BETWEEN DATEADD(MM, - 3, DATEADD(DD, - 1, GETDATE())) AND DATEADD(DD, - 1, GETDATE())
            )
    GROUP BY material, plant
    ), pppbo
AS (
    SELECT reorder3M / WDs AS reorderPerWDs, T1.material, T1.plant, bo3M / WDs AS boPerWDs, WDs
    FROM ppp T1
    LEFT JOIN backOrder T2 ON T1.material = T2.material AND T1.plant = T2.plant
    CROSS JOIN Tdate
        --ORDER BY plant, material
    ), T4fcst
    -- Table to make fcst table. FROM this month to upcoming 5 monthl
AS (
    SELECT material, SUM(eship) AS eship, FORMAT(act_date, 'MMyyyy') AS MMYYYY, plant
    FROM [ivy.mm.dim.factfcst]
    WHERE act_date BETWEEN DATEADD(DD, - DAY(GETDATE()), GETDATE()) AND DATEADD(MM, @mthwitdh+1, DATEADD(DD, - DAY(GETDATE
                            ()), GETDATE()))
    GROUP BY material, FORMAT(act_date, 'MMyyyy'), plant
    ), fcst
AS (
    SELECT T1.TheDate, T1.WDs, T1.accumWDs, T1.MMYYYY, T1.IsWeekend, (1 - IsWeekend) * (CONVERT(FLOAT, T2.eship) / CONVERT(FLOAT, T1.WDs)
            ) AS fcstPerWDs, T2.plant, T2.material
    FROM (
        SELECT TheDate, SUM(1 - IsWeekend) OVER (PARTITION BY MMYYYY) AS WDs, SUM(1 - IsWeekend) 
            OVER (
                PARTITION BY MMYYYY ORDER BY TheDate
                ) AS accumWDs, MMYYYY, IsWeekend
        FROM [ivy.mm.dim.date]
        WHERE thedate BETWEEN DATEADD(DD, - DAY(GETDATE()), GETDATE()) AND DATEADD(MM, @mthwitdh+1, DATEADD(DD, - DAY(
                                GETDATE()), GETDATE()))
        ) T1
    LEFT JOIN T4fcst T2 ON T1.MMYYYY = T2.MMYYYY
    WHERE thedate BETWEEN DATEADD(DAY, - 6, GETDATE()) AND DATEADD(MONTH, @mthwitdh, GETDATE())
    ), Tpoasn
AS (
    SELECT material, plant, act_date, sum(po_qty) AS po_qty, sum(asn_qty) AS asn_qty
    FROM [ivy.mm.dim.fact_poasn]
    WHERE po_num NOT LIKE '43%' -- exclude intra_company po
    GROUP BY material, plant, act_date
    ), mrp01 as (
        SELECT * FROM [ivy.mm.dim.mrp01]
    WHERE pgr != 'IEC' -- exclude IEC for total stock
    ), TOTAL
AS (
    SELECT T2.PL_plant, T1.thedate, T3.material, T3.nsp, T1.IsWeekend, T6.boPerWDs, T5.po_qty + T5.asn_qty AS 
        poasn_qty, T6.reorderPerWDs, T8.total_stock - T8.blocked - T8.subcont_qty AS On_hand_qty, T9.
        fcstPerWDs, T9.WDs, T9.accumWDs, T10.thisMthReOdqty
    FROM (
        SELECT DISTINCT PL_PLANT -- pl_plant
        FROM [ivy.mm.dim.mrp01]
        ) T2
    CROSS JOIN (
        SELECT THEDATE, IsWeekend
        FROM [ivy.mm.dim.date]
        WHERE thedate BETWEEN DATEADD(DAY, - 6, GETDATE()) AND DATEADD(MONTH, @mthwitdh, GETDATE())
        ) T1
    CROSS JOIN (
        SELECT MATERIAL, nsp --material
        FROM [ivy.mm.dim.mtrl]
        WHERE MS in ('01','03') --AND DIVISION = 'C2'
        
        ) T3
    LEFT JOIN Tpoasn T5 ON T3.material = T5.material -- poasn_qty
        AND T2.pl_plant = T5.plant AND T1.TheDate = T5.act_date
    LEFT JOIN pppbo T6 ON T3.material = T6.material -- average Monthly reorder qty
        AND T2.pl_plant = T6.plant
    LEFT JOIN mrp01 T8 ON T3.material = T8.material -- on_hand qty
        AND T2.pl_plant = T8.pl_plant
    LEFT JOIN fcst T9 ON T3.material = T9.material -- fcstPerWDs, isWeekend
        AND T2.pl_plant = T9.plant AND T9.TheDate = T1.TheDate
    LEFT JOIN pppDailyThisMonth T10 ON T10.material = T3.material AND T10.plant = T2.pl_plant
    -- WHERE T8.pgr != 'IEC' -- exclude IEC for total stock
        --LEFT JOIN [ivy.sd.fact.order] od ON od.act_date= T1.TheDate and od.material=T3.material
    ), TOTAL2
    -- NULL value to 0 (avgDbo, poasn_qty, avgDreorder, fcstPerWDs,On_hand_qty)
AS (
    SELECT pl_plant, TheDate, material, CASE WHEN nsp IS NULL THEN 0 ELSE nsp END AS nsp, CASE WHEN (boPerWDs IS NULL
                    ) THEN 0 ELSE boPerWDs END AS avgDbo, CASE WHEN (poasn_qty IS NULL) THEN 0 
            ELSE poasn_qty END AS poasn_qty, CASE WHEN (reorderPerWDs IS NULL) THEN 0 ELSE 
                reorderPerWDs END AS avgDreorder, CASE WHEN (fcstPerWDs IS NULL) THEN 0 
            ELSE fcstPerWDs END AS fcstPerWDs, CASE WHEN (On_hand_qty IS NULL) THEN 0 ELSE 
                On_hand_qty END AS On_hand_qty, CASE WHEN (thisMthReOdqty IS NULL) THEN 0 
            ELSE thisMthReOdqty END AS thisMthReOdqty, IsWeekend, WDs, accumWDs
    FROM Total
    )
SELECT pl_plant AS plant, TheDate, material AS mtrl, nsp, avgDbo, poasn_qty, avgDreorder, On_hand_qty, CASE WHEN (fcstPerWDs = 0 AND IsWeekend = 0 AND pl_plant IN ('1100', '1400')
                ) THEN avgDreorder + avgDbo ELSE fcstPerWDs END AS fcstD, thisMthReOdqty
FROM TOTAL2
ORDER BY plant, mtrl, TheDate
""", con=engine)
print("full table is ready")

df_wds = pd.read_sql("""
DECLARE @mthwitdh AS INT
SELECT @mthwitdh = 7;
With T1 AS(
SELECT TheDate, SUM(1 - IsWeekend) OVER (PARTITION BY MMYYYY) AS WDs, SUM(1 - IsWeekend) OVER (
        PARTITION BY MMYYYY ORDER BY TheDate
        ) AS accumWDs, IsWeekend
FROM [ivy.mm.dim.date]
WHERE thedate BETWEEN DATEADD(DD, - DAY(GETDATE()), GETDATE()) AND DATEADD(MM, @mthwitdh+1, DATEADD(DD, - DAY(GETDATE()), 
                    GETDATE()))
)
SELECT * FROM T1
WHERE thedate BETWEEN DATEADD(DAY, - 6, GETDATE()) AND DATEADD(MONTH, @mthwitdh, GETDATE())
ORDER BY TheDate
""", con=engine)

end = time.time()
timelist.append([end-start, "Get full table from SQL server"])
# %%
# define location
start = time.time()
file_loc = r'C:\Users\KISS Admin\Desktop\IVYENT_DH\P6. DailyDM except codes'
# file_loc = r'C:\Users\Public\Data\ESA\P6. DailyDM except codes'

# group by mtrl & TheDate

df_total = df_ft.groupby(["mtrl", "TheDate"]).agg({'nsp':'mean','avgDbo':'sum',"poasn_qty":'sum','avgDreorder':'sum','On_hand_qty':'sum','fcstD':'sum','thisMthReOdqty':'sum'})
# df_total = df_ft.groupby(["mtrl", "TheDate"]).sum()
df_total = df_total.reset_index()
df_total = df_total.merge(df_wds, how='left', on='TheDate')
# left join with df_wds
end = time.time()
timelist.append(
    [end-start, """df_total = df_ft.groupby(["mtrl", "TheDate"]).sum()"""])

# %%
# define DailyCalculate
start = time.time()

def DailyCalculate(df):
    half_flag = False
    if int(todays.strftime('%d')) > 15:
        print("The adjustment after half month on the starting month will be applied")
        half_flag = True
    # df = df.reset_index()

    df_mtrl = pd.DataFrame(df["mtrl"].unique())
    df_date = pd.DataFrame(df["TheDate"].unique())

    # set BOseq, residue, BOqty on df
    df["BOseq"] = 999
    df["residue"] = 999
    df["BOqty"] = 0
    df["BO$"] = 0
    df = df[['mtrl', 'TheDate', 'nsp', 'avgDbo', 'poasn_qty', 'avgDreorder', 'On_hand_qty', 'fcstD',
             "BOseq", "residue", "BOqty", "BO$", 'thisMthReOdqty', 'WDs', 'accumWDs']]
    # define po processing time as 5days
    poDays = 5

    df_mtrl = df_mtrl.to_numpy()

    colnames = df.columns
    df = df.to_numpy()

    for index_mtrl in range(len(df_mtrl)):
        if index_mtrl % 19 == 0:
            # print( f'{df_mtrl.loc[index_mtrl][0]:15} {float(index_mtrl+1)/float(len(df_mtrl))*100:.2f}% ') # print % progress
            # print % progress
            print(
                f'{df_mtrl[index_mtrl][0]:15} {float(index_mtrl+1)/float(len(df_mtrl))*100:.2f}% ')
        # set current BOflag, BOseq, Residue
        BOflag = 0
        curBOseq = 0
        # df.loc[index_mtrl*len(df_date), "On_hand_qty"]
        curResidue = df[index_mtrl*len(df_date)][6]
        # check if there is no poasn for this mtrl
        # poasn_test = df.loc[df["mtrl"] == df.loc[index_mtrl *len(df_date), "mtrl"], "poasn_qty"].sum() == 0
        poasn_test = df[df[:, 0] ==
                        df[index_mtrl * len(df_date), 0], 4].sum() == 0
        if (curResidue == 0 & poasn_test):  # if no inventory and poasn => set residue:0 and BOseq:-1
            # df.loc[index_mtrl*len(df_date):(index_mtrl+1) *	len(df_date)-1, "residue"] = 0
            df[index_mtrl*len(df_date):(index_mtrl+1) * len(df_date), 9] = 0
            # df.loc[index_mtrl*len(df_date):(index_mtrl+1) * len(df_date)-1, "BOseq"] = -1
            df[index_mtrl*len(df_date):(index_mtrl+1) * len(df_date), 8] = -1
        else:
            # df[index_mtrl*len(df_date):(index_mtrl+1)*len(df_date)]=CalcMtrl(df,index_mtrl,len(df_date),poDays,curBOseq,BOflag,curResidue)
            for index_date in range(5, len(df_date)):

                curIndex = index_mtrl*len(df_date)+index_date  # current Index
                # df.loc[curIndex,"On_hand_qty"]=curResidue+df.loc[curIndex-poDays,"poasn_qty"]
                curYMflag = (curYM == df[curIndex, 1].strftime('%Y%m'))
                if half_flag == True:  # halfday
                    # if df[curIndex,"fcstD"]*df[curIndex,accumWDs]<df[curIndex,thisMthReOdqty]:
                    if (df[curIndex, 7]*df[curIndex, 14] < df[curIndex, 12]) & curYMflag:
                        # print(f'{df[curIndex,7]}*{df[curIndex,14]}<{df[curIndex,12]}')
                        df[curIndex, 7] = df[curIndex, 12]/df[curIndex, 14]
                df[curIndex, 6] = curResidue+df[curIndex-poDays, 4]
                if BOflag == 1:  # BO status
                    # poasn comes => end of BO, set BOflag, BOseq as out of BO. calc. curResidue
                    if df[curIndex-poDays, 4] > 0:
                        BOflag = 0
                        # df.loc[curIndex, "BOseq"] = 0
                        df[curIndex, 8] = 0
                        # curResidue = curResidue + df.loc[curIndex-poDays, "poasn_qty"]-df.loc[curIndex, "fcstD"]
                        curResidue = curResidue + \
                            df[curIndex-poDays, 4]-df[curIndex, 7]
                    else:
                        df[curIndex, 8] = curBOseq
                else:  # not BO
                    # curResidue = curResidue + df.loc[curIndex-poDays, "poasn_qty"]-df.loc[curIndex,"fcstD"]
                    curResidue = curResidue + \
                        df[curIndex-poDays, 4]-df[curIndex, 7]
                    # Start of BO. +=1 BOseq. set curResidue, BOflag according to BO.
                    if curResidue <= 0:
                        curBOseq += 1
                        curResidue = 0
                        BOflag = 1
                        df[curIndex, 8] = curBOseq
                    else:  # curResidue >0 -> not BO
                        df[curIndex, 8] = 0
                # df.loc[curIndex, "residue"] = curResidue
                df[curIndex, 9] = curResidue

                # For BO days, set BOqty as fcstD, calc. BO$ = BOqty * nsp
                if df[curIndex, 8] != 0:
                    # df.loc[curIndex, "BOqty"]=df.loc[curIndex, "fcstD"]
                    df[curIndex, 10] = df[curIndex, 7]
                    # df.loc[curIndex, "BO$"]=df.loc[curIndex, "BOqty"]*df.loc[curIndex, "nsp"]
                    df[curIndex, 11] = df[curIndex, 10]*df[curIndex, 2]
                else:
                    df[curIndex, 10] = 0
    print("creating The result table was done")

    # calculate BO$. save Total DM table
    df = pd.DataFrame(df)
    df.columns = colnames

    df["BO$"] = df["BOqty"]*df["nsp"]
    # df=df.loc[df.BOseq!=999]
    return df


end = time.time()
timelist.append([end-start, "def DailyCalculate(df):"])

# %%
# apply DailyCalculate to df_total and save as csv

start = time.time()
todays = datetime.today().date()
today = todays.strftime('%Y-%m-%d')

df_total = DailyCalculate(df_total)
df_total = df_total[df_total['TheDate'] >= todays]

df_total.reset_index(inplace=True)
df_total.drop("index", axis=1, inplace=True)

total_loc = file_loc+"\\"+today+"_"+targetPlant+"_ESA.csv"

# TODO: remove after validation
validate_loc = file_loc+"\\"+today+"_"+targetPlant+"_4validate.csv"
df_total[['mtrl', 'TheDate', 'nsp', 'avgDbo', 'poasn_qty', 'avgDreorder', 'On_hand_qty', 'fcstD',
             "BOseq", "residue", "BOqty", "BO$", 'thisMthReOdqty', 'WDs', 'accumWDs']].to_csv(validate_loc, index=False)


# select to columns for export
df_total = df_total[['mtrl', 'TheDate', 'On_hand_qty',
                     'residue', 'fcstD',  'BOqty', 'BO$', 'BOseq']].copy()
df_total[['On_hand_qty','residue', 'fcstD',  'BOqty', 'BO$']]=df_total[['On_hand_qty','residue', 'fcstD',  'BOqty', 'BO$']].astype(np.float64).round(2)

df_total['loc']='total'
df_total.to_csv(total_loc, index=False)
print('exporting TotalESA.csv was done')

# Ending Inventory Schedule.csv
# residue_loc = file_loc+"\\"+today+"_"+targetPlant+"_Ending Inventory Schedule.csv"
# residue = df_total[["mtrl", "TheDate", "residue"]].copy()
# residue["residue"] = residue.loc[:, "residue"].apply(lambda x: round(x))
# residue.to_csv(residue_loc, index=False)
# print("Ending Inventory Schedule.csv was done")

end = time.time()
timelist.append([end-start, "caluculate Daily and to_csv result"])

# %%
# group by mtrl and BOseq to show summary data of BOdates and BOqty,BO$
# plot the BOdates, save the summary csv and png file
start = time.time()
todays = datetime.today()
today = todays.strftime('%Y-%m-%d')
# total_loc = file_loc+"\\"+today+"_"+targetPlant+"_ESA.csv"
df_total = pd.read_csv(total_loc)

df_result = df_total.groupby(['mtrl', 'BOseq']).agg(
    {'TheDate': ['min', 'count', 'max'], 'BOqty': ['sum'], 'BO$': 'sum'})
df_result = df_result.reset_index()
df_result.columns = ['mtrl', 'BOseq', 'StartDate',
                     '#ofBOdays', 'EndDate', 'BOqty', 'BO$']

# df_result1 = df_result[df_result.BOseq != 0].copy()
df_result1 = df_result.copy()
df_result1.loc[:, "StartDate"] = df_result1.loc[:,
                                                "StartDate"].apply(lambda x: pd.to_datetime(x))
df_result1["EndDate"] = df_result1.loc[:, "EndDate"].apply(
    lambda x: pd.to_datetime(x))

# df_result = summary_DM(df_total)
df_result1 = df_result1[['mtrl', 'BOseq', 'StartDate', 'EndDate',
                        '#ofBOdays', 'BOqty', 'BO$']]

df_result1 = df_result1[df_result.BOseq != 0].copy()
result_loc = file_loc+"\\"+today+"_"+targetPlant+"_BO.csv"

df_result1['loc']='total'
df_result1.to_csv(result_loc, index=False)
end = time.time()
timelist.append([end-start, "caluculate BO.csv"])

# %%
start = time.time()

def find1(df):
    for i in range(len(df)):
        if df[i]==1:
            return i
    return 0

df_sumBOseq = df_result.groupby('mtrl').agg({'BOseq': ['sum','count']})
df_sumBOseq=df_sumBOseq.reset_index()
df_sumBOseq.columns = ['mtrl', 'BOseq', 'count']
df_sumBOseq['mtrl_last_index']=(df_sumBOseq['count']).cumsum()-1
df_sumBOseq['loc1']=df_result.groupby('mtrl')['BOseq'].agg(lambda x: find1(list(x))).reset_index()['BOseq']

# absolute location of (BOseq==1) for each mtrl = mtrl_last_index-count+(loc1-1)

df_sumBOseq["StartDate"] = ''   # df_sumBOseq[index][5]
df_sumBOseq["ox"] = ""          # df_sumBOseq[index][6]

df_mtrl = pd.DataFrame(df_total["mtrl"].unique())
df_date = pd.DataFrame(df_total["TheDate"].unique())

len_mtrl=len(df_mtrl)
len_date=len(df_date)

colnames = df_sumBOseq.columns
df_sumBOseq=df_sumBOseq.to_numpy()

# for index, row in df_sumBOseq.iterrows():
for index in range(len(df_sumBOseq)):
    # if row.BOseq > 0:
    if df_sumBOseq[index][1]>0:
        # id = (df_result["mtrl"] == df_sumBOseq[index][0]) & (df_result["BOseq"] == 1)
        # absolute location of (BOseq==1) for each mtrl = mtrl_last_index-count+(loc1-1)        
        id = df_sumBOseq[index][3]-df_sumBOseq[index][4]+1
        # df_sumBOseq[index][5] = df_result.loc[id,"StartDate"].values[0]
        df_sumBOseq[index][5] = df_result.loc[id,"StartDate"]
        df_sumBOseq[index][6] = 'Y'
    # elif row.BOseq< 0:
    elif df_sumBOseq[index][1] < 0:
        df_sumBOseq[index][5] = today 
        df_sumBOseq[index][6] = 'Y'
    # elif row.BOseq == 0:
    elif df_sumBOseq[index][1] == 0:
        # lastday = df_total.loc[df_total.mtrl == df_sumBOseq[index][0]].iloc[-1]
        lastday = df_total.loc[len_date*(index+1)-1]
        # fcst=lastday.fcstD
        # if sum(df_total.loc[df_total.mtrl == df_sumBOseq[index][0], "fcstD"]) == 0:
        if sum(df_total.loc[len_date*index:len_date*(index+1)-1,'fcstD']) == 0:
            # inventory>0 but no fcst
            df_sumBOseq[index][5] = '2100-01-01'
            df_sumBOseq[index][6] = 'N'
        else:
            if lastday.fcstD == 0:
                fcsts=df_total.loc[len_date*index:len_date*(index+1)-1,'fcstD']
                # fcst = np.average(df_total.loc[(df_total.mtrl == df_sumBOseq[index][0]) & (df_total.fcstD > 0), "fcstD"].values)
                fcst = np.average(fcsts[fcsts>0])
            else:  # it means lastday.fcstD>0
                fcst = lastday.fcstD
            deltaD = lastday.residue/fcst
            if deltaD>1000:
                deltaD=1000
            bo = datetime.strptime(
                lastday.TheDate, '%Y-%m-%d')+timedelta(days=deltaD)
            df_sumBOseq[index][5] = datetime.strftime(
                bo, '%Y-%m-%d')
            df_sumBOseq[index][6] = 'N'
    else:
        print(df_sumBOseq[index])
        Print("debug needed")

df_sumBOseq= pd.DataFrame(df_sumBOseq)
df_sumBOseq.columns= colnames

# %%
BOdateloc = file_loc+"\\"+today+"_"+targetPlant+"_BOdate.csv"
df_sumBOseq['loc']='total'
df_sumBOseq[["mtrl", "StartDate", 'ox','loc']].to_csv(BOdateloc, index=False)

total_loc = file_loc+"\\"+today+"_"+targetPlant+"_ESA.csv"
df_total = df_total[['mtrl', 'TheDate', 'On_hand_qty',
                     'residue', 'fcstD',  'BOqty', 'BO$', 'BOseq','loc']].copy()
df_total.to_csv(total_loc, index=False)
print('exporting BOdate.csv was done')

end = time.time()
timelist.append([end-start, "caluculate BOdate.csv"])
# %%
# start = time.time()

# def draw_figure(df_result1_fig, loc):
#     plt.rcParams['figure.figsize'] = [8, len(df_result1_fig.mtrl)/5]
#     plt.xlim(min(df_result1_fig.StartDate), max(df_result1_fig.EndDate))
#     plt.barh(y=df_result1_fig.mtrl, width=df_result1_fig.StartDate, color='w')
#     plt.barh(y=df_result1_fig.mtrl, width=df_result1_fig.EndDate -
#              df_result1_fig.StartDate, left=df_result1_fig.StartDate, color='b')
#     plt.grid(True, axis='Y')
#     plt.margins(x=0, y=0.005)
#     plt.tight_layout(pad=0.8)
#     plt.savefig(loc)

# png_loc = file_loc+"\\"+today+"_"+targetPlant+"_BO.png"
# draw_figure(df_result1, png_loc)

# png_loc = file_loc+"\\"+today+"_"+targetPlant+"_BOwo-1.png"
# draw_figure(df_result1[df_result1.BOseq != -1], png_loc)

# end = time.time()
# timelist.append([end-start, "summary and graph"])
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
