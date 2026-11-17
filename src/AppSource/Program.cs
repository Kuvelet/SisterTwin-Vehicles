using System.Diagnostics;
using System.Text;
using System.Text.Json;

namespace SisterTwinLauncher;

static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        ApplicationConfiguration.Initialize();
        if (args.Length == 2 && args[0] == "--offline-preview")
        {
            // Packaging smoke test only: no timers, share reads, requests, or database access.
            using var form = new LauncherForm(true) { ShowInTaskbar = false, Opacity = 0 };
            form.Show();
            Application.DoEvents();
            using var bitmap = new Bitmap(form.Width, form.Height);
            form.DrawToBitmap(bitmap, new Rectangle(Point.Empty, form.Size));
            bitmap.Save(args[1], System.Drawing.Imaging.ImageFormat.Png);
            form.Close();
            return;
        }
        Application.Run(new LauncherForm());
    }
}

sealed record Snapshot(bool Online, string WorkerText, string State, string Message, string? ReportsFolder = null);

sealed class WorkerStatusDot : Control
{
    public WorkerStatusDot()
    {
        SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer, true);
        ForeColor = Color.Gray;
        TabStop = false;
        AccessibleName = "Worker status: checking";
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        e.Graphics.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
        float diameter = Math.Min(ClientSize.Width, ClientSize.Height) - 2;
        if (diameter <= 0) return;
        using var brush = new SolidBrush(ForeColor);
        e.Graphics.FillEllipse(brush, (ClientSize.Width - diameter) / 2, (ClientSize.Height - diameter) / 2, diameter, diameter);
    }
}

sealed class LauncherForm : Form
{
    private const string Root = @"\\FILESERVER\SisterTwin";
    private static readonly string ControlRoot = Path.Combine(Root, "Control");
    private static readonly string LocalFolder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SisterTwinLauncherLayout3");
    private static readonly string LastRequestFile = Path.Combine(LocalFolder, "last-request.txt");
    private readonly Label worker = new() { Text = "Checking worker...", AutoSize = true, ForeColor = Color.DimGray };
    private readonly WorkerStatusDot workerDot = new() { Size = new Size(12, 12), Anchor = AnchorStyles.Left, Margin = new Padding(0, 0, 7, 0) };
    private readonly Label state = new() { Text = "Ready", AutoSize = true, Font = new Font("Segoe UI", 20, FontStyle.Bold) };
    private readonly Label message = new() { Text = "", Dock = DockStyle.Fill, AutoEllipsis = true };
    private readonly Label requestLabel = new() { Text = "", AutoSize = true, ForeColor = Color.DimGray };
    private readonly ProgressBar progress = new() { Dock = DockStyle.Fill, Height = 12, Style = ProgressBarStyle.Blocks };
    private readonly Button generate = new() { Text = "Generate Reports", UseMnemonic = false, AutoSize = true, Padding = new Padding(12, 6, 12, 6), Enabled = false };
    private readonly Button reports = new() { Text = "Open Reports Folder", AutoSize = true, Padding = new Padding(12, 6, 12, 6) };
    private readonly System.Windows.Forms.Timer timer = new() { Interval = 2000 };
    private readonly InputPanel inputPanel = new();
    private readonly LiveLogPanel liveLog = new();
    private readonly TabPage liveLogTab;
    private string? requestId;
    private bool refreshing;
    private bool submitting;
    private bool online;
    private string currentState = "Ready";
    private bool firstRefresh = true;
    private string? completedReportsFolder;

    public LauncherForm() : this(false) { }

    internal LauncherForm(bool previewOnly)
    {
        Text = "Sister/Twin Reports";
        StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(960, 720);
        MinimumSize = new Size(860, 680);
        AutoScaleMode = AutoScaleMode.Dpi;
        Font = new Font("Segoe UI", 10);
        BackColor = Color.White;
        Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath) ?? SystemIcons.Application;

        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(24, 10, 24, 24), ColumnCount = 1, RowCount = 8 };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 60));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 32));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 42));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 24));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        var header = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1 };
        header.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        header.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 220));
        header.Controls.Add(new Label { Text = "Sister/Twin Reports", AutoSize = true, Anchor = AnchorStyles.Left, Font = new Font("Segoe UI", 19, FontStyle.Bold), ForeColor = Color.FromArgb(0, 82, 145) }, 0, 0);
        var logo = new PictureBox { Dock = DockStyle.Fill, SizeMode = PictureBoxSizeMode.Zoom, Margin = new Padding(12, 4, 0, 4) };
        using (var resource = typeof(LauncherForm).Assembly.GetManifestResourceStream("SisterTwin.Logo.png"))
        {
            if (resource is not null) { using var original = Image.FromStream(resource); logo.Image = new Bitmap(original); }
        }
        header.Controls.Add(logo, 1, 0);
        FormClosed += (_, _) => logo.Image?.Dispose();
        layout.Controls.Add(header, 0, 0);
        var workerStatus = new TableLayoutPanel { AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, Anchor = AnchorStyles.Top | AnchorStyles.Left, ColumnCount = 2, RowCount = 1, Margin = new Padding(3, 0, 3, 0) };
        workerStatus.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        workerStatus.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        workerStatus.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        worker.Margin = Padding.Empty;
        worker.Anchor = AnchorStyles.Left;
        workerStatus.Controls.Add(workerDot, 0, 0);
        workerStatus.Controls.Add(worker, 1, 0);
        layout.Controls.Add(workerStatus, 0, 1);
        layout.Controls.Add(state, 0, 2);
        layout.Controls.Add(message, 0, 3);
        layout.Controls.Add(inputPanel, 0, 4);
        layout.Controls.Add(progress, 0, 5);
        layout.Controls.Add(requestLabel, 0, 6);
        var commands = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Fill, WrapContents = true, Margin = new Padding(0, 12, 0, 0) };
        commands.Controls.AddRange([generate, reports]);
        layout.Controls.Add(commands, 0, 7);
        Controls.Add(layout);
        generate.BackColor = Color.FromArgb(0, 89, 156);
        generate.ForeColor = Color.White;
        generate.FlatStyle = FlatStyle.Flat;
        generate.FlatAppearance.BorderSize = 0;
        inputPanel.SelectionChanged += (_, _) => generate.Text = inputPanel.Selected is null ? "Generate Reports" : "Replace List & Generate";
        inputPanel.CurrentPath = Path.Combine(ControlRoot, "Data", "SisterTwin_Vehicles_Raw.csv");
        liveLogTab = inputPanel.AddView("Live Log", liveLog);

        try
        {
            if (!previewOnly && File.Exists(LastRequestFile))
            {
                string value = File.ReadAllText(LastRequestFile).Trim();
                if (IsId(value)) requestId = value;
            }
        }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }

        generate.Click += async (_, _) => await Submit();
        reports.Click += (_, _) => OpenFolder(completedReportsFolder ?? Path.Combine(Root, "Reports"));
        timer.Tick += async (_, _) => await RefreshStatus();
        if (!previewOnly)
            Shown += async (_, _) => { timer.Start(); await RefreshStatus(); await inputPanel.ReloadCurrent(); };
        FormClosed += (_, _) => timer.Dispose();
    }

    private static bool IsId(string value) => value.Length == 32 && value.All(c => c is >= '0' and <= '9' or >= 'a' and <= 'f');

    private static bool ResetCompletedOnOpen(bool opening, string status) => opening && status == "Completed";

    private static string TextValue(JsonElement element, string key, string fallback = "") =>
        element.TryGetProperty(key, out var value) && value.ValueKind == JsonValueKind.String ? value.GetString() ?? fallback : fallback;

    private static JsonDocument ReadJson(string path)
    {
        using var stream = SharedFiles.OpenRead(path);
        if (stream.Length > 65536) throw new IOException("Status file is unexpectedly large.");
        var document = JsonDocument.Parse(stream);
        if (document.RootElement.ValueKind != JsonValueKind.Object)
        {
            document.Dispose();
            throw new JsonException("Status must be a JSON object.");
        }
        return document;
    }

    private static Snapshot ReadSnapshot(string? id)
        => ReadSnapshotFrom(ControlRoot, id);

    private static Snapshot ReadSnapshotFrom(string controlRoot, string? id)
    {
        bool available = false;
        string workerText = "WORKERHOST: offline or not responding";
        try
        {
            using var document = ReadJson(Path.Combine(controlRoot, "worker.json"));
            var root = document.RootElement;
            bool fresh = DateTimeOffset.TryParse(TextValue(root, "updated_utc"), out var updated)
                && DateTimeOffset.UtcNow - updated < TimeSpan.FromSeconds(25)
                && DateTimeOffset.UtcNow - updated > TimeSpan.FromSeconds(-60);
            available = fresh && TextValue(root, "layout") == "compact-v1" && TextValue(root, "state") == "Online" && TextValue(root, "computer").Equals("WORKERHOST", StringComparison.OrdinalIgnoreCase);
            if (available) workerText = "WORKERHOST: online";
        }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
        catch (JsonException) { }
        if (id is null) return new Snapshot(available, workerText, "Ready", "");

        if (!IsId(id)) throw new IOException("Invalid request identifier.");
        string path = Path.Combine(controlRoot, "Runs", id, "status.json");
        if (File.Exists(path))
        {
            using var result = ReadJson(path);
            var root = result.RootElement;
            if (TextValue(root, "request_id") != id) throw new IOException("Request status does not match.");
            string status = TextValue(root, "status", "Unknown");
            string detail = TextValue(root, "message");
            if ((status is "Processing" or "Finishing") && !available)
                return new Snapshot(false, workerText, "Connection lost", "The worker is not responding. The run may still be active; do not submit it again yet.");
            string? folder = status == "Completed" ? SafeReportFolder(controlRoot, id, TextValue(root, "reports_folder")) : null;
            return new Snapshot(available, workerText, status, detail, folder);
        }
        if (File.Exists(Path.Combine(controlRoot, "Queue", id, "request.json")) || File.Exists(Path.Combine(controlRoot, "Runs", id, "request.json")))
            return new Snapshot(available, workerText, "Queued", available ? "Waiting for the worker." : "Waiting for WORKERHOST to reconnect.");
        return new Snapshot(available, workerText, "Unknown", "No status was found for this request. Ask the workflow owner to check before retrying.");
    }

    private static string? SafeReportFolder(string controlRoot, string id, string folder)
    {
        if (string.IsNullOrWhiteSpace(folder)) return null;
        try
        {
            string expectedParent = Path.GetFullPath(Path.Combine(controlRoot, "..", "Reports"));
            string full = Path.GetFullPath(folder);
            return string.Equals(Path.GetDirectoryName(full), expectedParent, StringComparison.OrdinalIgnoreCase)
                && Path.GetFileName(full).EndsWith("_" + id, StringComparison.Ordinal) ? full : null;
        }
        catch (ArgumentException) { return null; }
        catch (NotSupportedException) { return null; }
    }

    private async Task RefreshStatus()
    {
        if (refreshing || submitting || IsDisposed) return;
        refreshing = true;
        try
        {
            string? requested = requestId;
            var snapshot = await Task.Run(() => ReadSnapshot(requested));
            if (IsDisposed || requested != requestId) return;
            if (ResetCompletedOnOpen(firstRefresh, snapshot.State))
            {
                // Keep active requests across restarts, but do not reopen old completion screens.
                if (File.Exists(LastRequestFile)) File.Delete(LastRequestFile);
                requestId = null;
                snapshot = snapshot with { State = "Ready", Message = "", ReportsFolder = null };
            }
            bool showLog = firstRefresh && requestId is not null;
            firstRefresh = false;
            online = snapshot.Online;
            currentState = snapshot.State;
            completedReportsFolder = snapshot.ReportsFolder;
            worker.Text = snapshot.WorkerText;
            workerDot.ForeColor = online ? Color.FromArgb(0, 220, 90) : Color.FromArgb(255, 45, 75);
            workerDot.AccessibleName = online ? "Worker status: online" : "Worker status: offline or not responding";
            workerDot.Invalidate();
            state.Text = snapshot.State;
            message.Text = snapshot.Message;
            requestLabel.Text = requestId is null ? "" : "Request: " + requestId;
            state.ForeColor = snapshot.State switch { "Completed" => Color.DarkGreen, "Failed" or "Interrupted" => Color.Firebrick, _ => Color.Black };
            bool active = snapshot.State is "Processing" or "Finishing" or "Queued";
            var progressStyle = active ? ProgressBarStyle.Marquee : ProgressBarStyle.Blocks;
            if (progress.Style != progressStyle)
            {
                progress.Style = progressStyle;
                progress.MarqueeAnimationSpeed = active ? 30 : 0;
            }
            if (!active)
                progress.Value = snapshot.State == "Completed" ? 100 : 0;
            generate.Enabled = online && (snapshot.State is "Ready" or "Completed" or "Failed" or "Interrupted");
            inputPanel.SetInputEnabled(snapshot.State is "Ready" or "Completed" or "Failed" or "Interrupted");
            if (showLog) inputPanel.SelectView(liveLogTab);
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or JsonException)
        {
            worker.Text = "Shared folder unavailable";
            workerDot.ForeColor = Color.FromArgb(255, 45, 75);
            workerDot.AccessibleName = "Worker status: unavailable";
            workerDot.Invalidate();
            message.Text = error.Message;
            generate.Enabled = false;
        }
        finally
        {
            try { if (!IsDisposed) await liveLog.RefreshLog(ControlRoot, requestId, currentState, message.Text); }
            finally { refreshing = false; }
        }
    }

    private async Task Submit()
    {
        if (!online || submitting || refreshing) return;
        if (currentState == "Interrupted" && MessageBox.Show(this, "A previous run was interrupted. Has the workflow owner confirmed it is no longer running?", "Confirm before retrying", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes) return;
        CsvInput? selected = inputPanel.Selected;
        string confirmation = selected is null
            ? "Generate fresh reports on WORKERHOST using the current shared list? This refreshes the analysis tables."
            : $"Replace the shared vehicle list with {selected.Name} ({selected.Rows.Length:N0} pairs) and generate reports?\n\nThe worker will back up the previous CSV. This new list will also be used for future runs.\n\nFile checks do not confirm vehicle relationships or part interchangeability.";
        if (MessageBox.Show(this, confirmation, selected is null ? "Generate Reports" : "Replace shared vehicle list", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) return;
        submitting = true;
        generate.Enabled = false;
        inputPanel.SetInputEnabled(false);
        string id = Guid.NewGuid().ToString("N");
        try
        {
            await Task.Run(() =>
            {
                if (!ReadSnapshot(null).Online) throw new IOException("WORKERHOST is not responding. No request was sent.");
                PublishRequest(ControlRoot, id, selected, () =>
                {
                    Directory.CreateDirectory(LocalFolder);
                    File.WriteAllText(LastRequestFile, id);
                    requestId = id;
                });
            });
            currentState = "Queued";
            state.Text = "Queued";
            firstRefresh = false;
            inputPanel.MarkSubmitted();
            inputPanel.SelectView(liveLogTab);
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException)
        {
            MessageBox.Show(this, "The request could not be confirmed. Check its status before trying again.\n\n" + error.Message, "Request problem", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
        finally { submitting = false; }
        await RefreshStatus();
    }

    internal static void PublishRequest(string control, string id, CsvInput? selected, Action beforePublish)
    {
        if (!IsId(id)) throw new IOException("Invalid request identifier.");
        string queue = Path.Combine(control, "Queue");
        if (!Directory.Exists(queue)) throw new IOException("Queue unavailable. Ask the owner to start the worker.");
        string temporary = Path.Combine(queue, id + ".pending");
        string destination = Path.Combine(queue, id);
        if (Directory.Exists(temporary) || Directory.Exists(destination)) throw new IOException("Request already exists.");
        Directory.CreateDirectory(temporary);
        try
        {
            if (selected is not null) File.WriteAllBytes(Path.Combine(temporary, "input.csv"), selected.Content);
            string json = JsonSerializer.Serialize(new { version = 2, request_id = id, action = "generate_reports",
                requested_by = Environment.UserDomainName + "\\" + Environment.UserName,
                input_mode = selected is null ? "current" : "upload", csv_sha256 = selected?.Checksum });
            File.WriteAllText(Path.Combine(temporary, "request.json"), json, new UTF8Encoding(false));
            beforePublish();
            // Publish the complete folder at once; the worker ignores .pending folders.
            Directory.Move(temporary, destination);
        }
        catch
        {
            // Remove only our known unpublished files. A network error may leave a .pending folder.
            try
            {
                File.Delete(Path.Combine(temporary, "input.csv"));
                File.Delete(Path.Combine(temporary, "request.json"));
                if (Directory.Exists(temporary)) Directory.Delete(temporary);
            }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
            throw;
        }
    }

    private void OpenFolder(string path)
    {
        try
        {
            var start = new ProcessStartInfo("explorer.exe") { UseShellExecute = false };
            start.ArgumentList.Add(path);
            Process.Start(start);
        }
        catch (Exception error)
        {
            MessageBox.Show(this, error.Message, "Cannot open folder", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
    }
}
