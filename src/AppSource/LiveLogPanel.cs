using System.Text;
using System.Text.RegularExpressions;

namespace SisterTwinLauncher;

static class SharedFiles
{
    // Status writers replace files atomically; readers must allow delete sharing.
    internal static FileStream OpenRead(string path) => new(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
}

sealed record LogChunk(string Text, bool Reset, bool Waiting, bool More);

sealed class LiveLogReader
{
    private string? request;
    private long offset;
    private Decoder decoder = Encoding.UTF8.GetDecoder();
    internal LogChunk Read(string controlRoot, string? id)
    {
        bool reset = request != id;
        if (reset) { request = id; offset = 0; decoder.Reset(); }
        if (id is null) return new LogChunk("", true, false, false);
        if (!Regex.IsMatch(id, @"\A[0-9a-f]{32}\z")) throw new IOException("Invalid log request identifier.");
        string path = Path.Combine(controlRoot, "Runs", id, "workflow.log");
        FileStream stream;
        try { stream = SharedFiles.OpenRead(path); }
        catch (FileNotFoundException) { return new LogChunk("", reset, true, false); }
        catch (DirectoryNotFoundException) { return new LogChunk("", reset, true, false); }
        using (stream)
        {
            if (stream.Length < offset) { offset = 0; decoder.Reset(); reset = true; }
            string prefix = "";
            if (offset == 0 && stream.Length > 262144)
            {
                offset = stream.Length - 262144;
                prefix = "[Showing recent output. The full log remains saved.]\r\n";
                reset = true;
            }
            stream.Position = offset;
            byte[] buffer = new byte[65536];
            int count = stream.Read(buffer, 0, buffer.Length);
            offset += count;
            char[] characters = new char[Encoding.UTF8.GetMaxCharCount(count)];
            int decoded = decoder.GetChars(buffer, 0, count, characters, 0, false);
            return new LogChunk(prefix + new string(characters, 0, decoded), reset, false, offset < stream.Length);
        }
    }
}

sealed class LiveLogPanel : UserControl
{
    private readonly TextBox output = new() { Dock = DockStyle.Fill, Multiline = true, ReadOnly = true, WordWrap = false, ScrollBars = ScrollBars.Both, Font = new Font("Consolas", 10), BackColor = Color.FromArgb(247, 249, 251), BorderStyle = BorderStyle.FixedSingle };
    private readonly Label status = new() { Text = "No run selected", AutoSize = true, ForeColor = Color.DimGray };
    private readonly CheckBox follow = new() { Text = "Follow output", Checked = true, AutoSize = true };
    private readonly Button copy = new() { Text = "Copy displayed log", AutoSize = true, Enabled = false };
    private readonly LiveLogReader reader = new();
    private string? displayedRequest;

    internal LiveLogPanel()
    {
        Dock = DockStyle.Fill;
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 3, Padding = new Padding(8) };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        status.Margin = new Padding(0, 0, 0, 8);
        layout.Controls.Add(status, 0, 0);
        layout.Controls.Add(output, 0, 1);
        var commands = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, Padding = new Padding(0, 8, 0, 0) };
        commands.Controls.AddRange([follow, copy]);
        layout.Controls.Add(commands, 0, 2);
        Controls.Add(layout);
        copy.Click += (_, _) =>
        {
            try { if (output.TextLength > 0) Clipboard.SetText(output.Text); }
            catch (System.Runtime.InteropServices.ExternalException) { MessageBox.Show(this, "The clipboard is busy. Try again.", "Copy log"); }
        };
    }

    internal async Task RefreshLog(string controlRoot, string? id, string runState = "", string runMessage = "")
    {
        if (displayedRequest != id)
        {
            displayedRequest = id;
            output.Clear();
            copy.Enabled = false;
        }
        try
        {
            LogChunk chunk = await Task.Run(() => reader.Read(controlRoot, id));
            if (IsDisposed || displayedRequest != id) return;
            ApplyChunk(chunk);
            status.Text = id is null ? "No run selected" : chunk.Waiting ? "Waiting for worker output..." : chunk.More ? "Loading saved output..." : "Live log | refreshed every 2 seconds";
            if (chunk.Waiting && runState is "Failed" or "Interrupted")
            {
                status.Text = "No captured output is available for this run.";
                output.Text = runState + ": " + runMessage;
                copy.Enabled = output.TextLength > 0;
            }
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException)
        {
            if (!IsDisposed) status.Text = "Log unavailable. Retrying automatically.";
        }
    }

    internal void ApplyChunk(LogChunk chunk)
    {
        if (chunk.Reset) output.Clear();
        if (chunk.Text.Length > 0)
        {
            int selection = output.SelectionStart;
            int length = output.SelectionLength;
            output.AppendText(chunk.Text);
            int removed = Math.Max(0, output.TextLength - 300000);
            if (removed > 0) output.Text = output.Text[removed..];
            if (follow.Checked) { output.SelectionStart = output.TextLength; output.SelectionLength = 0; output.ScrollToCaret(); }
            else
            {
                int start = Math.Min(output.TextLength, Math.Max(0, selection - removed));
                output.Select(start, Math.Min(length, output.TextLength - start));
                output.ScrollToCaret();
            }
        }
        copy.Enabled = output.TextLength > 0;
    }
}
