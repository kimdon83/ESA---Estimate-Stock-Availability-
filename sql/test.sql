SELECT COUNT(*) FROM [ivy.mm.dim.mtrl] WHERE mg='pp'

SELECT TOP (5) * FROM [ivy.mm.dim.mrp01]
SELECT TOP (5) * FROM [ivy.mm.dim.mtrl]

SELECT distinct T2.material, T2. dlv_plant, T1. dlv_plant, T1.pdt FROM [ivy.mm.dim.mrp01] T1
INNER JOIN [ivy.mm.dim.mtrl] T2 on T1.material= T2.material and T1.dlv_plant=T2.dlv_plant
and T2.dlv_plant= T1.pl_plant
WHERE mg!='pp' and T2.material in (SELECT material FROM [ivy.mm.dim.mtrl])
ORDER BY t2.material

SELECT material, pl_plant, dlv_plant, pdt FROM [ivy.mm.dim.mrp01]
ORDER BY material

SELECT material, dlv_plant FROM [ivy.mm.dim.mtrl]

SELECT MATERIAL FROM [ivy.mm.dim.mrp01]
SELECT DISTINCT MATERIAL FROM [ivy.mm.dim.mrp01]

SELECT MATERIAL FROM [ivy.mm.dim.mtrl]
SELECT DISTINCT MATERIAL FROM [ivy.mm.dim.mtrl]

SELECT distinct pl_plant FROM [ivy.mm.dim.mrp01] ORDER BY pl_plant
SELECT distinct dlv_plant FROM [ivy.mm.dim.mrp01] ORDER BY dlv_plant
SELECT distinct dlv_plant FROM [ivy.mm.dim.mtrl] ORDER BY dlv_plant

SELECT * FROM [ivy.mm.dim.mtrl] WHERE dlv_plant=1500

SELECT distinct material FROM [ivy.mm.dim.mtrl] WHERE mg!='pp'

SELECT distinct dlv_plant FROM [ivy.mm.dim.mrp01]

SELECT material, pdt,dlv_plant FROM [ivy.mm.dim.mtrl]
WHERE mg!='pp'



SELECT * FROM [ivy.mm.dim.mtrl] T1
LEFT JOIN [ivy.mm.dim.mrp01] T2 on T1.material= T2.material and T1 
WHERE mg!='pp'


