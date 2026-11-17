

CREATE   PROCEDURE [dbo].[usp_CreateSisterTwin_DescriptionGapReport_v7]
AS
BEGIN
    SET NOCOUNT ON;

    DROP TABLE IF EXISTS dbo.SisterTwin_DescriptionGapReport_v7;
    DROP TABLE IF EXISTS #FinalOutputWithMissingRegion;
    DROP TABLE IF EXISTS #FinalOutputWithIDs;
    DROP TABLE IF EXISTS #GapPartCoverage;
    DROP TABLE IF EXISTS #RankedReferenceVehicles;

    WITH TwinVehicles_Expanded AS
    (
        SELECT DISTINCT
            TRY_CONVERT(int, [Year]) AS [Year],
            LTRIM(RTRIM(Make_A)) AS Make_A,
            LTRIM(RTRIM(Model_A)) AS Model_A,
            LTRIM(RTRIM(Make_B)) AS Make_B,
            LTRIM(RTRIM(Model_B)) AS Model_B
        FROM dbo.SisterTwin_Vehicles_Raw_Expanded_VCDB
        WHERE TRY_CONVERT(int, [Year]) IS NOT NULL
          AND LTRIM(RTRIM([ACES_Status])) = 'ACES Valid'
    ),
    AppDescriptions AS
    (
        SELECT DISTINCT
            [Archetype],
            [Make],
            [Model],
            TRY_CONVERT(int, [Year]) AS [Year],
            [Part Number] AS [Part],
            [PartGroup],
            [Category],
            [Description],
            [Position],
            [cid],
            [Engine],
            [Engine Designation],
            [EngineMake],
            [EngineVIN],
            [Region],
            [Submodel],
            [Air],
            [Aspiration],
            [BodyStyle],
            [BrakeType],
            [CarbNumber],
            [CarbType],
            [Color],
            [Connection Type],
            [Cylinder Head Type],
            [Drive Type],
            [Emissions],
            [FootNote],
            [Fuel System],
            [Fuel Type],
            [Lead Length],
            [Note],
            [OE Number],
            [Quantity],
            [Split Year],
            [Transmission],
            [Vendor],
            [Supersession Note],
            [ESN Range]
        FROM [CatalogDb].[dbo].[PIM_BaseApplications]
        WHERE [Description] IS NOT NULL
          AND TRY_CONVERT(int, [Year]) IS NOT NULL
    ),
    MissingVehicleRegions AS
    (
        SELECT DISTINCT
            [Make],
            [Model],
            TRY_CONVERT(int, [Year]) AS [Year],
            [Engine],
            [Region] AS [Missing Region]
        FROM [ProductManagementDb].[dbo].[v_PIM_Vehicle_Dictionary]
        WHERE TRY_CONVERT(int, [Year]) IS NOT NULL
    ),
    A_Descriptions AS
    (
        SELECT
            t.Make_A,
            t.Model_A,
            t.Make_B,
            t.Model_B,
            a.[Archetype],
            a.[Make],
            a.[Model],
            a.[Year],
            a.[Part],
            a.[PartGroup],
            a.[Category],
            a.[Description],
            a.[Position],
            a.[cid],
            a.[Engine],
            a.[Engine Designation],
            a.[EngineMake],
            a.[EngineVIN],
            a.[Region],
            a.[Submodel],
            a.[Air],
            a.[Aspiration],
            a.[BodyStyle],
            a.[BrakeType],
            a.[CarbNumber],
            a.[CarbType],
            a.[Color],
            a.[Connection Type],
            a.[Cylinder Head Type],
            a.[Drive Type],
            a.[Emissions],
            a.[FootNote],
            a.[Fuel System],
            a.[Fuel Type],
            a.[Lead Length],
            a.[Note],
            a.[OE Number],
            a.[Quantity],
            a.[Split Year],
            a.[Transmission],
            a.[Vendor],
            a.[Supersession Note],
            a.[ESN Range]
        FROM TwinVehicles_Expanded AS t
        INNER JOIN AppDescriptions AS a
            ON a.[Make] = t.Make_A
           AND a.[Model] = t.Model_A
           AND a.[Year] = t.[Year]
    ),
    B_Descriptions AS
    (
        SELECT
            t.Make_A,
            t.Model_A,
            t.Make_B,
            t.Model_B,
            b.[Archetype],
            b.[Make],
            b.[Model],
            b.[Year],
            b.[Part],
            b.[PartGroup],
            b.[Category],
            b.[Description],
            b.[Position],
            b.[cid],
            b.[Engine],
            b.[Engine Designation],
            b.[EngineMake],
            b.[EngineVIN],
            b.[Region],
            b.[Submodel],
            b.[Air],
            b.[Aspiration],
            b.[BodyStyle],
            b.[BrakeType],
            b.[CarbNumber],
            b.[CarbType],
            b.[Color],
            b.[Connection Type],
            b.[Cylinder Head Type],
            b.[Drive Type],
            b.[Emissions],
            b.[FootNote],
            b.[Fuel System],
            b.[Fuel Type],
            b.[Lead Length],
            b.[Note],
            b.[OE Number],
            b.[Quantity],
            b.[Split Year],
            b.[Transmission],
            b.[Vendor],
            b.[Supersession Note],
            b.[ESN Range]
        FROM TwinVehicles_Expanded AS t
        INNER JOIN AppDescriptions AS b
            ON b.[Make] = t.Make_B
           AND b.[Model] = t.Model_B
           AND b.[Year] = t.[Year]
    ),
    MissingFromB AS
    (
        SELECT
            a.[Make],
            a.[Model],
            a.Make_B AS [Missing Make],
            a.Model_B AS [Missing Model],
            a.[Year],
            a.[Archetype],
            a.[Part],
            a.[PartGroup],
            a.[Category],
            a.[Description],
            a.[Position],
            a.[cid],
            a.[Engine],
            a.[Engine Designation],
            a.[EngineMake],
            a.[EngineVIN],
            a.[Region],
            a.[Submodel],
            a.[Air],
            a.[Aspiration],
            a.[BodyStyle],
            a.[BrakeType],
            a.[CarbNumber],
            a.[CarbType],
            a.[Color],
            a.[Connection Type],
            a.[Cylinder Head Type],
            a.[Drive Type],
            a.[Emissions],
            a.[FootNote],
            a.[Fuel System],
            a.[Fuel Type],
            a.[Lead Length],
            a.[Note],
            a.[OE Number],
            a.[Quantity],
            a.[Split Year],
            a.[Transmission],
            a.[Vendor],
            a.[Supersession Note],
            a.[ESN Range]
        FROM A_Descriptions AS a
        LEFT JOIN B_Descriptions AS b
            ON b.Make_A = a.Make_A
           AND b.Model_A = a.Model_A
           AND b.Make_B = a.Make_B
           AND b.Model_B = a.Model_B
           AND b.[Year] = a.[Year]
           AND b.[Description] = a.[Description]
        WHERE b.[Description] IS NULL
    ),
    MissingFromA AS
    (
        SELECT
            b.[Make],
            b.[Model],
            b.Make_A AS [Missing Make],
            b.Model_A AS [Missing Model],
            b.[Year],
            b.[Archetype],
            b.[Part],
            b.[PartGroup],
            b.[Category],
            b.[Description],
            b.[Position],
            b.[cid],
            b.[Engine],
            b.[Engine Designation],
            b.[EngineMake],
            b.[EngineVIN],
            b.[Region],
            b.[Submodel],
            b.[Air],
            b.[Aspiration],
            b.[BodyStyle],
            b.[BrakeType],
            b.[CarbNumber],
            b.[CarbType],
            b.[Color],
            b.[Connection Type],
            b.[Cylinder Head Type],
            b.[Drive Type],
            b.[Emissions],
            b.[FootNote],
            b.[Fuel System],
            b.[Fuel Type],
            b.[Lead Length],
            b.[Note],
            b.[OE Number],
            b.[Quantity],
            b.[Split Year],
            b.[Transmission],
            b.[Vendor],
            b.[Supersession Note],
            b.[ESN Range]
        FROM B_Descriptions AS b
        LEFT JOIN A_Descriptions AS a
            ON a.Make_A = b.Make_A
           AND a.Model_A = b.Model_A
           AND a.Make_B = b.Make_B
           AND a.Model_B = b.Model_B
           AND a.[Year] = b.[Year]
           AND a.[Description] = b.[Description]
        WHERE a.[Description] IS NULL
    ),
    FinalOutput AS
    (
        SELECT
            [Make],
            [Model],
            [Missing Make],
            [Missing Model],
            [Year],
            [Archetype],
            [Part],
            [PartGroup],
            [Category],
            [Description],
            [Position],
            [cid],
            [Engine],
            [Engine Designation],
            [EngineMake],
            [EngineVIN],
            [Region],
            [Submodel],
            [Air],
            [Aspiration],
            [BodyStyle],
            [BrakeType],
            [CarbNumber],
            [CarbType],
            [Color],
            [Connection Type],
            [Cylinder Head Type],
            [Drive Type],
            [Emissions],
            [FootNote],
            [Fuel System],
            [Fuel Type],
            [Lead Length],
            [Note],
            [OE Number],
            [Quantity],
            [Split Year],
            [Transmission],
            [Vendor],
            [Supersession Note],
            [ESN Range]
        FROM MissingFromB

        UNION ALL

        SELECT
            [Make],
            [Model],
            [Missing Make],
            [Missing Model],
            [Year],
            [Archetype],
            [Part],
            [PartGroup],
            [Category],
            [Description],
            [Position],
            [cid],
            [Engine],
            [Engine Designation],
            [EngineMake],
            [EngineVIN],
            [Region],
            [Submodel],
            [Air],
            [Aspiration],
            [BodyStyle],
            [BrakeType],
            [CarbNumber],
            [CarbType],
            [Color],
            [Connection Type],
            [Cylinder Head Type],
            [Drive Type],
            [Emissions],
            [FootNote],
            [Fuel System],
            [Fuel Type],
            [Lead Length],
            [Note],
            [OE Number],
            [Quantity],
            [Split Year],
            [Transmission],
            [Vendor],
            [Supersession Note],
            [ESN Range]
        FROM MissingFromA
    )
    SELECT
        f.[Make],
        f.[Model],
        f.[Missing Make],
        f.[Missing Model],
        f.[Year],
        f.[Archetype],
        f.[Part],
        f.[PartGroup],
        f.[Category],
        f.[Description],
        f.[Position],
        f.[cid],
        f.[Engine],
        f.[Engine Designation],
        f.[EngineMake],
        f.[EngineVIN],
        f.[Region] AS [Reference Region],
        r.[Missing Region],
        f.[Submodel],
        f.[Air],
        f.[Aspiration],
        f.[BodyStyle],
        f.[BrakeType],
        f.[CarbNumber],
        f.[CarbType],
        f.[Color],
        f.[Connection Type],
        f.[Cylinder Head Type],
        f.[Drive Type],
        f.[Emissions],
        f.[FootNote],
        f.[Fuel System],
        f.[Fuel Type],
        f.[Lead Length],
        f.[Note],
        f.[OE Number],
        f.[Quantity],
        f.[Split Year],
        f.[Transmission],
        f.[Vendor],
        f.[Supersession Note],
        f.[ESN Range]
    INTO #FinalOutputWithMissingRegion
    FROM FinalOutput AS f
    LEFT JOIN MissingVehicleRegions AS r
        ON r.[Make] = f.[Missing Make]
       AND r.[Model] = f.[Missing Model]
       AND r.[Year] = f.[Year]
       AND ISNULL(r.[Engine], '') = ISNULL(f.[Engine], '');

    -- A complete reference must contain the union of all eligible reference parts.
    SELECT
        [Missing Make],
        [Missing Model],
        [Year],
        [Description],
        COUNT(DISTINCT [Part]) AS RequiredPartCount,
        MAX(CASE WHEN NULLIF(LTRIM(RTRIM([Part])), '') IS NULL THEN 1 ELSE 0 END) AS HasMissingPartNumber
    INTO #GapPartCoverage
    FROM #FinalOutputWithMissingRegion
    WHERE [Missing Region] IS NOT NULL
    GROUP BY
        [Missing Make],
        [Missing Model],
        [Year],
        [Description];

    -- Count distinct parts separately from application rows used for tie-breaking.
    WITH ReferenceVehicleEngineCoverage AS
    (
        SELECT
            [Missing Make],
            [Missing Model],
            [Year],
            [Description],
            [Make],
            [Model],
            COUNT(*) AS EligibleApplicationRowCount,
            COUNT(DISTINCT [Part]) AS ReferencePartCount,
            MAX
            (
                CASE
                    WHEN NULLIF(LTRIM(RTRIM([Engine])), '') IS NULL THEN 1
                    ELSE 0
                END
            ) AS HasBlankEngine,
            MAX
            (
                CASE
                    WHEN NULLIF(LTRIM(RTRIM([Engine])), '') IS NOT NULL THEN 1
                    ELSE 0
                END
            ) AS HasSpecifiedEngine
        FROM #FinalOutputWithMissingRegion
        WHERE [Missing Region] IS NOT NULL
        GROUP BY
            [Missing Make],
            [Missing Model],
            [Year],
            [Description],
            [Make],
            [Model]
    ),
    CompleteReferenceVehicles AS
    (
        SELECT ReferenceCoverage.*
        FROM ReferenceVehicleEngineCoverage AS ReferenceCoverage
        INNER JOIN #GapPartCoverage AS GapCoverage
            ON GapCoverage.[Missing Make] = ReferenceCoverage.[Missing Make]
           AND GapCoverage.[Missing Model] = ReferenceCoverage.[Missing Model]
           AND GapCoverage.[Year] = ReferenceCoverage.[Year]
           AND GapCoverage.[Description] = ReferenceCoverage.[Description]
        WHERE ReferenceCoverage.ReferencePartCount = GapCoverage.RequiredPartCount
          AND GapCoverage.HasMissingPartNumber = 0
    ),
    RankedReferenceVehicles AS
    (
        SELECT
            [Missing Make],
            [Missing Model],
            [Year],
            [Description],
            [Make],
            [Model],
            ROW_NUMBER() OVER
            (
                PARTITION BY
                    [Missing Make],
                    [Missing Model],
                    [Year],
                    [Description]
                ORDER BY
                    CASE
                        WHEN HasBlankEngine = 1 AND HasSpecifiedEngine = 0 THEN 1
                        WHEN HasBlankEngine = 0 AND HasSpecifiedEngine = 1 THEN 2
                        ELSE 3
                    END,
                    EligibleApplicationRowCount DESC,
                    [Make],
                    [Model]
            ) AS ReferenceSelectionRank
        FROM CompleteReferenceVehicles
    )
    SELECT *
    INTO #RankedReferenceVehicles
    FROM RankedReferenceVehicles;

    SELECT
        DENSE_RANK() OVER
        (
            ORDER BY
                [Make],
                [Model],
                [Missing Make],
                [Missing Model],
                [Year],
                [Description],
                [Part]
        ) AS GapGroupID,

        DENSE_RANK() OVER
        (
            ORDER BY
                [Make],
                [Model],
                [Missing Make],
                [Missing Model],
                [Year],
                [Description],
                [Part],
                ISNULL([Missing Region], '')
        ) AS MissingRegionGroupID,

        CASE
            WHEN CandidateApplication.[Missing Region] IS NULL
                THEN 'Exclude - Missing Region is NULL'
            WHEN EXISTS
            (
                SELECT 1
                FROM #GapPartCoverage AS GapCoverage
                WHERE GapCoverage.[Missing Make] = CandidateApplication.[Missing Make]
                  AND GapCoverage.[Missing Model] = CandidateApplication.[Missing Model]
                  AND GapCoverage.[Year] = CandidateApplication.[Year]
                  AND GapCoverage.[Description] = CandidateApplication.[Description]
                  AND GapCoverage.HasMissingPartNumber = 1
            )
                THEN 'Needs review - missing part number'
            WHEN NOT EXISTS
            (
                SELECT 1
                FROM #RankedReferenceVehicles AS CompleteReference
                WHERE CompleteReference.[Missing Make] = CandidateApplication.[Missing Make]
                  AND CompleteReference.[Missing Model] = CandidateApplication.[Missing Model]
                  AND CompleteReference.[Year] = CandidateApplication.[Year]
                  AND CompleteReference.[Description] = CandidateApplication.[Description]
            )
                THEN 'Needs review - no reference contains all eligible parts'
            WHEN EXISTS
            (
                SELECT 1
                FROM #RankedReferenceVehicles AS SelectedReference
                WHERE SelectedReference.ReferenceSelectionRank = 1
                  AND SelectedReference.[Missing Make] = CandidateApplication.[Missing Make]
                  AND SelectedReference.[Missing Model] = CandidateApplication.[Missing Model]
                  AND SelectedReference.[Year] = CandidateApplication.[Year]
                  AND SelectedReference.[Description] = CandidateApplication.[Description]
                  AND SelectedReference.[Make] = CandidateApplication.[Make]
                  AND SelectedReference.[Model] = CandidateApplication.[Model]
            )
                THEN 'Include - selected reference vehicle'
            ELSE 'Exclude - another reference vehicle selected'
        END AS [Inclusion Decision],

        [Make],
        [Model],
        [Missing Make],
        [Missing Model],
        [Year],
        [Archetype],
        [Part],
        [PartGroup],
        [Category],
        [Description],
        [Position],
        [cid],
        [Engine],
        [Engine Designation],
        [EngineMake],
        [EngineVIN],
        [Reference Region],
        [Missing Region],
        [Submodel],
        [Air],
        [Aspiration],
        [BodyStyle],
        [BrakeType],
        [CarbNumber],
        [CarbType],
        [Color],
        [Connection Type],
        [Cylinder Head Type],
        [Drive Type],
        [Emissions],
        [FootNote],
        [Fuel System],
        [Fuel Type],
        [Lead Length],
        [Note],
        [OE Number],
        [Quantity],
        [Split Year],
        [Transmission],
        [Vendor],
        [Supersession Note],
        [ESN Range]
    INTO #FinalOutputWithIDs
    FROM #FinalOutputWithMissingRegion AS CandidateApplication;

    CREATE INDEX IX_FinalOutputWithIDs_GroupIDs
        ON #FinalOutputWithIDs
        (
            GapGroupID,
            MissingRegionGroupID
        );

    WITH MissingRegionGroupRows AS
    (
        SELECT
            GapGroupID,
            MissingRegionGroupID,
            COUNT(*) AS RowsInMissingRegionGroup
        FROM #FinalOutputWithIDs
        GROUP BY
            GapGroupID,
            MissingRegionGroupID
    ),
    ExpansionStats AS
    (
        SELECT
            f.GapGroupID,
            COUNT(*) AS GapGroupRowCount,
            COUNT(DISTINCT f.MissingRegionGroupID) AS MissingRegionGroupCount,
            MAX(r.RowsInMissingRegionGroup) AS MaxRowsInMissingRegionGroup
        FROM #FinalOutputWithIDs AS f
        INNER JOIN MissingRegionGroupRows AS r
            ON r.GapGroupID = f.GapGroupID
           AND r.MissingRegionGroupID = f.MissingRegionGroupID
        GROUP BY
            f.GapGroupID
    )
    SELECT
        f.GapGroupID,
        f.MissingRegionGroupID,

        CASE
            WHEN s.GapGroupRowCount = 1
                THEN 'No expansion'

            WHEN s.MissingRegionGroupCount > 1
             AND s.MaxRowsInMissingRegionGroup > 1
                THEN 'Expanded by missing region and application details'

            WHEN s.MissingRegionGroupCount > 1
                THEN 'Expanded by missing region'

            WHEN s.MaxRowsInMissingRegionGroup > 1
                THEN 'Expanded by application details'

            ELSE 'Expanded by duplicate/detail rows'
        END AS [Expansion Reason],

        f.[Inclusion Decision],

        f.[Make],
        f.[Model],
        f.[Missing Make],
        f.[Missing Model],
        f.[Year],
        f.[Archetype],
        f.[Part],
        f.[PartGroup],
        f.[Category],
        f.[Description],
        f.[Position],
        f.[cid],
        f.[Engine],
        f.[Engine Designation],
        f.[EngineMake],
        f.[EngineVIN],
        f.[Reference Region],
        f.[Missing Region],
        f.[Submodel],
        f.[Air],
        f.[Aspiration],
        f.[BodyStyle],
        f.[BrakeType],
        f.[CarbNumber],
        f.[CarbType],
        f.[Color],
        f.[Connection Type],
        f.[Cylinder Head Type],
        f.[Drive Type],
        f.[Emissions],
        f.[FootNote],
        f.[Fuel System],
        f.[Fuel Type],
        f.[Lead Length],
        f.[Note],
        f.[OE Number],
        f.[Quantity],
        f.[Split Year],
        f.[Transmission],
        f.[Vendor],
        f.[Supersession Note],
        f.[ESN Range]
    INTO dbo.SisterTwin_DescriptionGapReport_v7
    FROM #FinalOutputWithIDs AS f
    INNER JOIN ExpansionStats AS s
        ON s.GapGroupID = f.GapGroupID;

    -- Compile the result query after rebuilding the table with its current columns.
    EXEC sys.sp_executesql N'
    SELECT
        GapGroupID,
        MissingRegionGroupID,
        [Expansion Reason],
        [Inclusion Decision],
        [Make],
        [Model],
        [Missing Make],
        [Missing Model],
        [Year],
        [Archetype],
        [Part],
        [PartGroup],
        [Category],
        [Description],
        [Position],
        [cid],
        [Engine],
        [Engine Designation],
        [EngineMake],
        [EngineVIN],
        [Reference Region],
        [Missing Region],
        [Submodel],
        [Air],
        [Aspiration],
        [BodyStyle],
        [BrakeType],
        [CarbNumber],
        [CarbType],
        [Color],
        [Connection Type],
        [Cylinder Head Type],
        [Drive Type],
        [Emissions],
        [FootNote],
        [Fuel System],
        [Fuel Type],
        [Lead Length],
        [Note],
        [OE Number],
        [Quantity],
        [Split Year],
        [Transmission],
        [Vendor],
        [Supersession Note],
        [ESN Range]
    FROM dbo.SisterTwin_DescriptionGapReport_v7
    ORDER BY
        GapGroupID,
        MissingRegionGroupID,
        [Make],
        [Model],
        [Missing Make],
        [Missing Model],
        [Year],
        [Description],
        [Part],
        [Missing Region];';
END;
