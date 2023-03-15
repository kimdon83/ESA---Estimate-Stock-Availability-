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
# Connect to KIRA server
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
time2 = time.time()
print(f"{time2-start:.4f}sec")
# %%
# get the full table for this calcutation. 
print("start to read full table")
df_ft = pd.read_sql("""
WITH
	Tdate AS (
			SELECT COUNT(*) AS WDs
			FROM [ivy.mm.dim.date]
			WHERE isweekend != 1
				AND thedate BETWEEN DATEADD(MM, - 3, DATEADD(DD, - 1, GETDATE()))
			AND DATEADD(DD, - 1, GETDATE())
			GROUP BY IsWeekend

	),	ppp
	--avgMreorder within 3month, material, plant FROM [dbo].[bill_ppp]
	AS
	(
		SELECT SUM(qty) AS reorder3M, material, plant
		FROM ppp_temp
		WHERE act_date BETWEEN DATEADD(MM, - 3, DATEADD(DD, - 1, GETDATE()))
			AND DATEADD(DD, - 1, GETDATE())
			AND ordsqc > 1
		GROUP BY material, plant
	),
	backOrder
	-- avgMbo within 3month, material, plant FROM [ivy.sd.fact.bo] 
	AS
	(
		SELECT SUM(bo_qty) AS bo3M, material, plant
		FROM [ivy.sd.fact.bo]
		WHERE (
			act_date BETWEEN DATEADD(MM, - 3, DATEADD(DD, - 1, GETDATE()))
			AND DATEADD(DD, - 1, GETDATE())
			)
		GROUP BY material, plant
	), pppbo as (
	SELECT reorder3M / WDs as reorderPerWDs, T1.material, T1.plant, bo3M / WDs as boPerWDs
	, WDs FROM ppp T1
	Left Join backOrder T2 on T1.material=T2.material and T1.plant= T2.plant
	CROSS JOIN Tdate
	--ORDER BY plant, material
	),
	T4fcst
	-- Table to make fcst table. FROM this month to upcoming 5 monthl
	AS
	(
		SELECT material, SUM(eship) AS eship , FORMAT(act_date, 'MMyyyy') AS MMYYYY, plant
		FROM [ivy.mm.dim.factfcst]
		WHERE act_date BETWEEN DATEADD(DD, - DAY(GETDATE()), GETDATE())
				AND DATEADD(MM, 7, DATEADD(DD, - DAY(GETDATE()), GETDATE()))
		GROUP BY material,FORMAT(act_date, 'MMyyyy'), plant
	),	fcst	AS	(
		SELECT T1.TheDate, T1.WDs, T1.MMYYYY, T1.IsWeekend, CONVERT(FLOAT, T2.eship) / CONVERT(FLOAT, T1.WDs) AS fcstPerWDs, T2.plant, T2.material
		FROM (
		SELECT TheDate, COUNT(*) OVER (PARTITION BY MMYYYY) AS WDs, MMYYYY, IsWeekend
			FROM [ivy.mm.dim.date]
			WHERE isweekend != 1
				AND thedate BETWEEN DATEADD(DD, - DAY(GETDATE()), GETDATE())
				AND DATEADD(MM, 7, DATEADD(DD, - DAY(GETDATE()), GETDATE()))
		) T1
			LEFT JOIN T4fcst T2 ON T1.MMYYYY = T2.MMYYYY
		WHERE  thedate BETWEEN DATEADD(DAY,-6, GETDATE())
	AND DATEADD(MONTH, 6, GETDATE())
	) ,	Tpoasn	as
	(
		SELECT material, plant, act_date, sum(po_qty) as po_qty, sum(asn_qty) as asn_qty
		FROM [ivy.mm.dim.fact_poasn]
		GROUP BY material, plant, act_date
	),	TOTAL	AS	(
		SELECT T2.PL_plant, T1.thedate, T3.material, T3.nsp, T1.IsWeekend, T6.boPerWDs, T5.po_qty + T5.asn_qty AS poasn_qty, T6.reorderPerWDs,
		T8.total_stock - T8.blocked - T8.subcont_qty AS On_hand_qty, T9.fcstPerWDs, T9.WDs
		FROM (
		SELECT DISTINCT PL_PLANT			-- pl_plant
			FROM [ivy.mm.dim.mrp01]
		) T2
	CROSS JOIN ( SELECT THEDATE, IsWeekend 	FROM [ivy.mm.dim.date] 
    	WHERE thedate BETWEEN DATEADD(DAY,-6, GETDATE())	AND DATEADD(MONTH, 6, GETDATE())		) T1
	CROSS JOIN ( SELECT MATERIAL, nsp			--material
			FROM [ivy.mm.dim.mtrl]	WHERE MS = '01' AND DIVISION = 'C2'
		) T3
			LEFT JOIN Tpoasn T5 ON T3.material = T5.material -- poasn_qty
				AND T2.pl_plant = T5.plant
				AND T1.TheDate = T5.act_date
			LEFT JOIN pppbo T6 ON T3.material = T6.material -- average Monthly reorder qty
				AND T2.pl_plant = T6.plant
			LEFT JOIN [ivy.mm.dim.mrp01] T8 ON T3.material = T8.material -- on_hand qty
				AND T2.pl_plant = T8.pl_plant
			LEFT JOIN fcst T9 ON T3.material = T9.material -- fcstPerWDs, isWeekend
				AND T2.pl_plant = T9.plant
				AND T9.TheDate = T1.TheDate
	),
	TOTAL2
	-- NULL value to 0 (avgDbo, poasn_qty, avgDreorder, fcstPerWDs,On_hand_qty)
	AS
	(
		SELECT pl_plant, TheDate, material
        , CASE WHEN nsp is NULL THEN 0 ELSE nsp END as nsp
	    , CASE WHEN (boPerWDs IS NULL)	THEN 0	ELSE boPerWDs	END AS avgDbo
        , CASE WHEN (poasn_qty IS NULL) THEN 0	ELSE poasn_qty	END AS poasn_qty
        , CASE WHEN (reorderPerWDs IS NULL) THEN 0 ELSE reorderPerWDs END AS avgDreorder
        , CASE WHEN (fcstPerWDs IS NULL)	THEN 0 ELSE fcstPerWDs 	END AS fcstPerWDs
        , CASE WHEN (On_hand_qty IS NULL)	THEN 0 ELSE On_hand_qty	END AS On_hand_qty,
			IsWeekend
		FROM Total
	)
SELECT pl_plant as plant, TheDate, material as mtrl, nsp, avgDbo, poasn_qty, avgDreorder, On_hand_qty,
	CASE WHEN (fcstPerWDs=0 and IsWeekend=0 and pl_plant in (1100,1400) ) THEN avgDreorder+avgDbo else fcstPerWDs END AS fcstD,
	avgDbo+avgDreorder as demandD
FROM TOTAL2
ORDER BY plant, mtrl, TheDate
""", con=engine)
time1 = time.time()
print(f"{time1-start:.4f}sec")
time.sleep(1)
# %%
# group by mtrl & TheDate
# df = df_ft.groupby(["mtrl", "TheDate"]).sum()
# df = df.reset_index()

df_1000=df_ft[df_ft["plant"]=="1000"]
df_1100=df_ft[df_ft["plant"]=="1100"]
df_1110=df_ft[df_ft["plant"]=="1110"]
df_1400=df_ft[df_ft["plant"]=="1400"]
df_1410=df_ft[df_ft["plant"]=="1410"]

df=df_1000

df_mtrl= pd.DataFrame(df.mtrl.unique())
df_date= pd.DataFrame(df.TheDate.unique())

# set BOseq, residue, BOqty on df

df["BOseq"] = 999
df["residue"] = 999
df["BOqty"]=0
# %%
# define po processing time as 5days
poDays=5
for index_mtrl in range(len(df_mtrl)):
    print( f'{df_mtrl.loc[index_mtrl][0]:15} {float(index_mtrl+1)/float(len(df_mtrl))*100:.2f}% ') # print % progress
	# set current BOflag, BOseq, Residue
    BOflag = 0
    curBOseq = 0
    curResidue = df.loc[index_mtrl*len(df_date), "On_hand_qty"]
	# check if there is no poasn for this mtrl
    poasn_test = df.loc[df["mtrl"] == df.loc[index_mtrl *len(df_date), "mtrl"], "poasn_qty"].sum() == 0 
    if(curResidue == 0 & poasn_test): # if no inventory and poasn => set residue:0 and BOseq:-1
        df.loc[index_mtrl*len(df_date):(index_mtrl+1) *
               len(df_date)-1, "residue"] = 0
        df.loc[index_mtrl*len(df_date):(index_mtrl+1) *
               len(df_date)-1, "BOseq"] = -1 # TODO : this needs discu
    else:
        for index_date in range(5,len(df_date)):
            curIndex = index_mtrl*len(df_date)+index_date # current Index
			# TODO : po point only for on hand qty. On hand qty : qty at start of the day 
            df.loc[curIndex,"On_hand_qty"]=curResidue+df.loc[curIndex-poDays,"poasn_qty"] 
            if BOflag == 1: # BO status
                if df.loc[curIndex-poDays, "poasn_qty"] > 0: # poasn comes => end of BO, set BOflag, BOseq as out of BO. calc. curResidue
                    BOflag = 0
                    df.loc[curIndex, "BOseq"] = 0
                    curResidue = curResidue + \
                        df.loc[curIndex-poDays, "poasn_qty"]-df.loc[curIndex, "fcstD"] # TODO: po point for curResidue
                else:
                    df.loc[curIndex, "BOseq"] = curBOseq # TODO : check at debug 
            else: # not BO
                curResidue = curResidue + \
                    df.loc[curIndex-poDays, "poasn_qty"]-df.loc[curIndex,
                                                         "fcstD"]  # TODO: po point for curResidue. calc. cur residue 
                if curResidue <= 0: # Start of BO. +=1 BOseq. set curResidue, BOflag according to BO.
                    curBOseq += 1
                    curResidue = 0
                    BOflag = 1
                    df.loc[curIndex, "BOseq"] = curBOseq
                else: # curResidue >0 -> not BO
                    df.loc[curIndex, "BOseq"] = 0
            df.loc[curIndex, "residue"] = curResidue

			# For BO days, set BOqty as fcstD, calc. BO$ = BOqty * nsp
            if df.loc[curIndex, "BOseq"]!=0:
                df.loc[curIndex, "BOqty"]=df.loc[curIndex, "fcstD"]
                df.loc[curIndex, "BO$"]=df.loc[curIndex, "BOqty"]*df.loc[curIndex, "nsp"]
            else:
                df.loc[curIndex, "BOqty"]=0


print("creating The result table was done")
time2 = time.time()
print(f"{time2-start:.4f}sec")
# %%
#calculate BO$. save Total DM table
df["BO$"]=df["BOqty"]*df["nsp"]
df=df.loc[df.BOseq!=999]
print(df)
df.to_csv('TotalDailyDM.csv')
#df.to_csv(r'Y:\OM ONLY_Shared Documents\5 Reports with Power Query\Source Data\PyCodes\dailyDM\TotalDailyDM.csv')
print('exporting TotalDailyDM.csv was done')

# %%
# group by mtrl and BOseq to show summary data of BOdates and BOqty,BO$
# plot the BOdates, save the summary csv and png file
import pandas as pd
df=pd.read_csv('TotalDailyDM.csv')

df_result = df.groupby(['mtrl', 'BOseq']).agg({'TheDate': ['min', 'count', 'max'],'BOqty':['sum'],'BO$':'sum'})
df_result = df_result.reset_index()
df_result.columns=['mtrl','BOseq','StartDate','#ofBOdays','EndDate','BOqty','BO$']

df_result1=df_result[df_result.BOseq!=0] 
df_result1.to_csv('TotalBOresults.csv')
# df_result1.to_csv(r'C:\Users\dokim2\Desktop\dokim2\2022\7\results\TotalBOresults.csv')
#df_result1.reset_index(inplace=True)
df_result1["StartDate"]=pd.to_datetime(df_result1.StartDate)
df_result1["EndDate"]=pd.to_datetime(df_result1.EndDate)

import matplotlib.pyplot as plt
maxlen=df_result1["mtrl"].apply(len).max()
plt.figure(figsize=(8,len(df_result1.mtrl)/5))
plt.xlim(min(df_result1.StartDate),max(df_result1.EndDate))
plt.barh(y=df_result1.mtrl,width=df_result1.StartDate,color='w')
plt.barh(y=df_result1.mtrl,width=df_result1.EndDate-df_result1.StartDate, left=df_result1.StartDate,color='b')
#plt.subplots_adjust(left=(maxlen+2)*0.011,bottom=1,top=0)
plt.subplots_adjust(left=0,bottom=0,top=1,right=1)
plt.grid(True,axis='x')
plt.margins(y=0.005)
#plt.show()
# TODO size and save debug
plt.savefig('TotalBOresults.png')
#plt.savefig(r'C:\Users\dokim2\Desktop\dokim2\2022\7\results\TotalBOresults.png')
# %%
print("end")
time3 = time.time()
print(f"{time3-start:.4f}sec")
