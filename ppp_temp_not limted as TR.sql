-- DELETE FROM ppp_temp
DROP TABLE ppp_temp

GO
;
WITH T1
AS (
    SELECT act_date, (CASE WHEN t2.bom_comp_material IS NOT NULL THEN t2.bom_comp_material ELSE t1.material END
            ) AS material, t1.shiptoparty, po_num, t1.plant, po_type, t3.cg_key,
        -- Calculate values  bom price rate / qty  bom qty rate
        (
            CASE WHEN t2.bom_comp_material IS NOT NULL THEN t1.gross_amt * t2.bom_price_rate ELSE t1.gross_amt 
                END
            ) AS gross_amt, (CASE WHEN t2.bom_comp_material IS NOT NULL THEN t1.qty * t2.bom_rate ELSE t1.qty END
            ) AS qty
    FROM [ivy.sd.fact.bill] t1
    LEFT JOIN [ivy.mm.dim.bom] t2 ON t1.material = t2.bom_parent_material LEFT JOIN [ivy.mm.dim.shiptoparty] t3 ON t1.shiptoparty=t3.shiptoparty 
    WHERE t3.cg_key='TR' -- TR fillter
    ), T2
AS (
    SELECT act_date, material, plant, po_num, po_type, shiptoparty, gross_amt, qty, DENSE_RANK() OVER (
            PARTITION BY material, shiptoparty ORDER BY act_date ASC
            ) ordsqc,
            cg_key
    FROM T1
    )
SELECT *
INTO ppp_temp
FROM T2;

GO

SELECT TOP (5) * FROM ppp_temp

