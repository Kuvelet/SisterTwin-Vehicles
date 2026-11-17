-- Reconstructed from inspected raw-input column metadata; no data included.
-- Run only in your configured catalog database.
IF OBJECT_ID(N'dbo.SisterTwin_Vehicles_Raw', N'U') IS NULL
BEGIN
CREATE TABLE dbo.SisterTwin_Vehicles_Raw (
    [Years] nvarchar(50) NOT NULL,
    [Make_A] nvarchar(50) NOT NULL,
    [Model_A] nvarchar(50) NOT NULL,
    [Make_B] nvarchar(50) NOT NULL,
    [Model_B] nvarchar(50) NOT NULL
);
END;
