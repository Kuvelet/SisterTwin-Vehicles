using System.Text;

namespace SisterTwinLauncher;

sealed class InputPanel : UserControl
{
    private readonly Button choose = new() { Text = "Choose CSV...", AutoSize = true };
    private readonly Button reset = new() { Text = "Use Current List", AutoSize = true, Enabled = false };
    private readonly Label source = new() { Text = "Current shared list", AutoSize = true, Font = new Font("Segoe UI", 11, FontStyle.Bold) };
    private readonly Label detail = new() { Text = "SisterTwin_Vehicles_Raw.csv", AutoSize = true, ForeColor = Color.DimGray };
    private readonly DataGridView grid = NewGrid();
    internal CsvInput? Selected { get; private set; }
    internal string? CurrentPath { get; set; }
    internal event EventHandler? SelectionChanged;

    internal TabPage AddView(string title, Control content)
    {
        var page = new TabPage(title) { BackColor = Color.White };
        page.Controls.Add(content);
        ((TabControl)Controls[0]).TabPages.Add(page);
        return page;
    }

    internal void SelectView(TabPage page) => ((TabControl)Controls[0]).SelectedTab = page;

    internal void SetInputEnabled(bool enabled)
    {
        choose.Enabled = enabled;
        reset.Enabled = enabled && Selected is not null;
    }

    internal InputPanel()
    {
        Dock = DockStyle.Fill;
        var tabs = new TabControl { Dock = DockStyle.Fill };
        var input = new TabPage("Vehicle List") { BackColor = Color.White, Padding = new Padding(12) };
        var format = new TabPage("CSV Format") { BackColor = Color.White, Padding = new Padding(12) };
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 4 };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        var buttons = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, WrapContents = true, Padding = new Padding(0, 8, 0, 8) };
        var template = new Button { Text = "Download Template...", AutoSize = true };
        template.Click += (_, _) => SaveTemplate();
        buttons.Controls.AddRange([choose, reset, template]);
        layout.Controls.Add(source, 0, 0);
        layout.Controls.Add(detail, 0, 1);
        layout.Controls.Add(buttons, 0, 2);
        foreach (string name in CsvInput.Columns) grid.Columns.Add(name, name);
        grid.ColumnHeadersDefaultCellStyle.ForeColor = Color.Black;
        grid.ColumnHeadersDefaultCellStyle.SelectionBackColor = grid.ColumnHeadersDefaultCellStyle.BackColor;
        grid.ColumnHeadersDefaultCellStyle.SelectionForeColor = grid.ColumnHeadersDefaultCellStyle.ForeColor;
        layout.Controls.Add(grid, 0, 3);
        input.Controls.Add(layout);

        var guide = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 4 };
        guide.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        guide.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        guide.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        guide.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        guide.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        guide.Controls.Add(new Label { Text = "Required columns", AutoSize = true, Font = new Font("Segoe UI", 11, FontStyle.Bold), Margin = new Padding(0, 0, 0, 10) }, 0, 0);
        var schema = NewGrid();
        schema.ColumnHeadersDefaultCellStyle.ForeColor = Color.Black;
        schema.ColumnHeadersDefaultCellStyle.SelectionBackColor = schema.ColumnHeadersDefaultCellStyle.BackColor;
        schema.ColumnHeadersDefaultCellStyle.SelectionForeColor = schema.ColumnHeadersDefaultCellStyle.ForeColor;
        schema.Columns.Add("Column", "Column");
        schema.Columns.Add("Value", "Required value");
        schema.Columns.Add("Example", "Example");
        schema.Rows.Add("Years", "YYYY or YYYY-YYYY (inclusive)", "2009-2016");
        schema.Rows.Add("Make_A", "Reference pair: first make", "Audi");
        schema.Rows.Add("Model_A", "Reference pair: first model", "Q7");
        schema.Rows.Add("Make_B", "Reference pair: second make", "Porsche");
        schema.Rows.Add("Model_B", "Reference pair: second model", "Cayenne");
        schema.Columns[1].FillWeight = 180;
        guide.Controls.Add(schema, 0, 1);
        guide.Controls.Add(new Label { Text = "All fields required | 50 characters per field | 2 MB | 10,000 pairs maximum\nComma-delimited CSV | UTF-8 or Windows-1252", AutoSize = true, Margin = new Padding(0, 10, 0, 8) }, 0, 2);
        guide.Controls.Add(new Label { Text = "Candidate relationships require expert review. VCdb matching does not confirm part interchangeability.", AutoSize = true, MaximumSize = new Size(740, 0), ForeColor = Color.DimGray }, 0, 3);
        format.Controls.Add(guide);
        tabs.TabPages.AddRange([input, format]);
        Controls.Add(tabs);
        choose.Click += async (_, _) => await Choose();
        reset.Click += async (_, _) => { ClearSelection(); await ReloadCurrent(); };
        Resize += (_, _) =>
        {
            source.MaximumSize = new Size(Math.Max(300, Width - 50), 0);
            detail.MaximumSize = new Size(Math.Max(300, Width - 50), 0);
        };
    }

    private static DataGridView NewGrid() => new()
    {
        Dock = DockStyle.Fill, ReadOnly = true, AllowUserToAddRows = false, AllowUserToDeleteRows = false,
        RowHeadersVisible = false, AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill,
        BackgroundColor = Color.White, BorderStyle = BorderStyle.FixedSingle,
        SelectionMode = DataGridViewSelectionMode.FullRowSelect, MultiSelect = false,
        AutoSizeRowsMode = DataGridViewAutoSizeRowsMode.DisplayedCells,
        DefaultCellStyle = new DataGridViewCellStyle { WrapMode = DataGridViewTriState.True, Padding = new Padding(4) },
        ColumnHeadersDefaultCellStyle = new DataGridViewCellStyle { BackColor = Color.FromArgb(236, 240, 244), Font = new Font("Segoe UI", 9, FontStyle.Bold) },
        EnableHeadersVisualStyles = false,
        ColumnHeadersHeightSizeMode = DataGridViewColumnHeadersHeightSizeMode.AutoSize
    };

    private async Task Choose()
    {
        using var dialog = new OpenFileDialog { Filter = "CSV files (*.csv)|*.csv", Title = "Choose sister/twin vehicle list", CheckFileExists = true };
        if (dialog.ShowDialog(this) != DialogResult.OK) return;
        Enabled = false;
        try
        {
            CsvInput value = await Task.Run(() => CsvInput.Load(dialog.FileName));
            if (!IsDisposed) ShowInput(value);
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or ArgumentException)
        { MessageBox.Show(this, error.Message, "CSV not accepted", MessageBoxButtons.OK, MessageBoxIcon.Warning); }
        finally { if (!IsDisposed) Enabled = true; }
    }

    internal void ShowInput(CsvInput value)
    {
        Selected = value;
        source.Text = "New list: " + value.Name;
        source.AutoEllipsis = true;
        detail.Text = $"{value.Rows.Length:N0} pairs | {value.ExpandedYears:N0} pair-years | Format checked, not yet uploaded";
        grid.Rows.Clear();
        foreach (var row in value.Rows) grid.Rows.Add(row.Cast<object>().ToArray());
        reset.Enabled = true;
        SelectionChanged?.Invoke(this, EventArgs.Empty);
    }

    internal void ClearSelection()
    {
        Selected = null;
        source.Text = "Current shared list";
        detail.Text = "SisterTwin_Vehicles_Raw.csv";
        grid.Rows.Clear();
        reset.Enabled = false;
        SelectionChanged?.Invoke(this, EventArgs.Empty);
    }

    internal void MarkSubmitted()
    {
        if (Selected is not null)
        {
            source.Text = "Submitted: " + Selected.Name;
            detail.Text = $"{Selected.Rows.Length:N0} pairs | {Selected.ExpandedYears:N0} pair-years";
        }
        Selected = null;
        reset.Enabled = false;
        SelectionChanged?.Invoke(this, EventArgs.Empty);
    }

    internal async Task ReloadCurrent()
    {
        if (CurrentPath is null || Selected is not null) return;
        try
        {
            CsvInput current = await Task.Run(() => CsvInput.Load(CurrentPath));
            if (IsDisposed || Selected is not null || source.Text.StartsWith("Submitted:")) return;
            source.Text = "Current shared list";
            detail.Text = $"{current.Name} | {current.Rows.Length:N0} pairs | {current.ExpandedYears:N0} pair-years";
            grid.Rows.Clear();
            foreach (var row in current.Rows) grid.Rows.Add(row.Cast<object>().ToArray());
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or ArgumentException)
        {
            if (!IsDisposed && Selected is null) detail.Text = "Current list preview unavailable. " + error.Message;
        }
    }

    private void SaveTemplate()
    {
        using var dialog = new SaveFileDialog { Filter = "CSV files (*.csv)|*.csv", FileName = "SisterTwin_Vehicles_Template.csv", AddExtension = true };
        if (dialog.ShowDialog(this) != DialogResult.OK) return;
        try { File.WriteAllText(dialog.FileName, string.Join(",", CsvInput.Columns) + "\r\n", new UTF8Encoding(true)); }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException)
        { MessageBox.Show(this, error.Message, "Cannot save template", MessageBoxButtons.OK, MessageBoxIcon.Warning); }
    }
}
