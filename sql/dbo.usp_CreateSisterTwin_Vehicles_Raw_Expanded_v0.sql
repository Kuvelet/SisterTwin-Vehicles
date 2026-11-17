

CREATE   PROCEDURE dbo.usp_CreateSisterTwin_Vehicles_Raw_Expanded_v0

AS

BEGIN

    SET NOCOUNT ON;



    DROP TABLE IF EXISTS dbo.SisterTwin_Vehicles_Raw_Expanded;



    WITH CleanTwins AS

    (

        SELECT

            TRY_CONVERT

            (

                int,

                LEFT

                (

                    REPLACE(REPLACE(Years, N'–', '-'), N'—', '-'),

                    4

                )

            ) AS StartYear,



            TRY_CONVERT

            (

                int,

                RIGHT

                (

                    REPLACE(REPLACE(Years, N'–', '-'), N'—', '-'),

                    4

                )

            ) AS EndYear,



            LTRIM(RTRIM(Make_A)) AS Make_A,

            LTRIM(RTRIM(Model_A)) AS Model_A,

            LTRIM(RTRIM(Make_B)) AS Make_B,

            LTRIM(RTRIM(Model_B)) AS Model_B,

            LTRIM(RTRIM(Years)) AS OriginalYearRange

        FROM dbo.SisterTwin_Vehicles_Raw

    ),

    YearNumbers AS

    (

        SELECT 0 AS n



        UNION ALL



        SELECT n + 1

        FROM YearNumbers

        WHERE n < 149

    )

    SELECT

        CleanTwins.Make_A,

        CleanTwins.Model_A,

        CleanTwins.Make_B,

        CleanTwins.Model_B,

        CleanTwins.OriginalYearRange,

        CleanTwins.StartYear,

        CleanTwins.EndYear,

        CleanTwins.StartYear + YearNumbers.n AS [Year]

    INTO dbo.SisterTwin_Vehicles_Raw_Expanded

    FROM CleanTwins

    INNER JOIN YearNumbers

        ON CleanTwins.StartYear + YearNumbers.n <= CleanTwins.EndYear

    WHERE CleanTwins.StartYear IS NOT NULL

      AND CleanTwins.EndYear IS NOT NULL

      AND CleanTwins.EndYear >= CleanTwins.StartYear

    OPTION (MAXRECURSION 150);



    SELECT

        Make_A,

        Model_A,

        Make_B,

        Model_B,

        OriginalYearRange,

        StartYear,

        EndYear,

        [Year]

    FROM dbo.SisterTwin_Vehicles_Raw_Expanded

    ORDER BY

        Make_A,

        Model_A,

        Make_B,

        Model_B,

        [Year];

END;
