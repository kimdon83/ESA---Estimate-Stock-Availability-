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