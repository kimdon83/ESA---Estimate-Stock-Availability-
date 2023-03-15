GO

DROP Table ppp_temp

SELECT * INTO ppp_temp FROM bill_ppp

GO

SELECT TOP(10) * FROM ppp_temp