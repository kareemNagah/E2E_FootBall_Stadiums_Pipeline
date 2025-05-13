use stadiums_db

SELECT TOP(10) 
    * 
FROM stadiums

-- Total capacity for each region 
SELECT 
    region,
    SUM(capacity) AS TotalCapacity
FROM stadiums
GROUP BY region 
ORDER BY SUM(capacity) DESC

-- Total capacity for each country 
SELECT 
    country,
    SUM(capacity) AS TotalCapacity
FROM stadiums
GROUP BY country 
ORDER BY SUM(capacity) DESC ;

-- Total capacity in Egypt
WITH Total_BY_Region AS (
SELECT 
    country,
    SUM(capacity) AS TotalCapacity
FROM stadiums
GROUP BY country )  
SELECT * FROM Total_BY_Region
WHERE country = 'Egypt' ;


-- Number of stadiums in each country 

SELECT 
    country,
    COUNT(capacity) AS TotalCapacity
FROM stadiums
GROUP BY country 
ORDER BY COUNT(capacity) DESC ;

-- Rank stadiums based on capacity

SELECT 
    region,
    stadiums,
    capacity,
    RANK() OVER(PARTITION BY region ORDER BY capacity DESC ) as Region_rank
FROM stadiums




