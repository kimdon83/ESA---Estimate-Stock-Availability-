With T1 AS(
SELECT TheDate, SUM(1 - IsWeekend) OVER (PARTITION BY MMYYYY) AS WDs, SUM(1 - IsWeekend) OVER (
        PARTITION BY MMYYYY ORDER BY TheDate
        ) AS accumWDs, IsWeekend
FROM [ivy.mm.dim.date]
WHERE thedate BETWEEN DATEADD(DD, - DAY(GETDATE()), GETDATE()) AND DATEADD(MM, 7, DATEADD(DD, - DAY(GETDATE()), 
                    GETDATE()))
)
SELECT * FROM T1
WHERE thedate BETWEEN DATEADD(DAY, - 6, GETDATE()) AND DATEADD(MONTH, 6, GETDATE())
ORDER BY TheDate