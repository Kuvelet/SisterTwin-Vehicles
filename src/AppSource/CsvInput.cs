using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using Microsoft.VisualBasic.FileIO;

namespace SisterTwinLauncher;

sealed record CsvInput(string Name, string[][] Rows, int ExpandedYears, byte[] Content)
{
    internal static readonly string[] Columns = ["Years", "Make_A", "Model_A", "Make_B", "Model_B"];
    internal const int MaxBytes = 2 * 1024 * 1024;
    internal string Checksum => Convert.ToHexString(SHA256.HashData(Content)).ToLowerInvariant();

    internal static CsvInput Load(string path)
    {
        using var stream = File.OpenRead(path);
        if (stream.Length > MaxBytes) throw new InvalidDataException("CSV must be no larger than 2 MB.");
        using var memory = new MemoryStream();
        byte[] buffer = new byte[8192];
        int count;
        while ((count = stream.Read(buffer)) > 0)
        {
            if (memory.Length + count > MaxBytes) throw new InvalidDataException("CSV must be no larger than 2 MB.");
            memory.Write(buffer, 0, count);
        }
        return Parse(Path.GetFileName(path), memory.ToArray());
    }

    internal static CsvInput Parse(string name, byte[] bytes)
    {
        if (bytes.Length == 0 || bytes.Length > MaxBytes) throw new InvalidDataException("CSV must be nonempty and no larger than 2 MB.");
        Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);
        var legacy = Encoding.GetEncoding(1252, EncoderFallback.ExceptionFallback, DecoderFallback.ExceptionFallback);
        string text;
        try { text = new UTF8Encoding(false, true).GetString(bytes).TrimStart('\uFEFF'); }
        catch (DecoderFallbackException) { text = legacy.GetString(bytes); }
        using var parser = new TextFieldParser(new StringReader(text)) { TextFieldType = FieldType.Delimited, HasFieldsEnclosedInQuotes = true, TrimWhiteSpace = false };
        parser.SetDelimiters(",");
        try
        {
            var headers = parser.ReadFields();
            if (headers is null || headers.Length != 5 || headers.Distinct().Count() != 5 || !Columns.All(headers.Contains))
                throw new InvalidDataException("Headers must be: Years, Make_A, Model_A, Make_B, Model_B.");
            int[] indices = Columns.Select(column => Array.IndexOf(headers, column)).ToArray();
            var rows = new List<string[]>();
            int expanded = 0;
            while (!parser.EndOfData)
            {
                var fields = parser.ReadFields();
                int rowNumber = rows.Count + 2;
                if (fields is null || fields.Length != 5) throw new InvalidDataException($"Row {rowNumber}: expected five fields.");
                var row = indices.Select(i => fields[i]).ToArray();
                for (int i = 0; i < row.Length; i++)
                {
                    if (string.IsNullOrWhiteSpace(row[i])) throw new InvalidDataException($"Row {rowNumber}: {Columns[i]} is blank.");
                    if (row[i].Length > 50) throw new InvalidDataException($"Row {rowNumber}: {Columns[i]} exceeds 50 characters.");
                    if (row[i].Any(char.IsControl)) throw new InvalidDataException($"Row {rowNumber}: {Columns[i]} contains a line break or control character.");
                }
                var match = Regex.Match(row[0].Replace('\u2013', '-').Replace('\u2014', '-'), @"\A([0-9]{4})(?:\s*-\s*([0-9]{4}))?\z");
                if (!match.Success) throw new InvalidDataException($"Row {rowNumber}: use YYYY or YYYY-YYYY for Years.");
                int start = int.Parse(match.Groups[1].Value);
                int end = match.Groups[2].Success ? int.Parse(match.Groups[2].Value) : start;
                if (end < start || end - start >= 150) throw new InvalidDataException($"Row {rowNumber}: year range must be ascending and at most 150 years.");
                expanded += end - start + 1;
                rows.Add(row);
                if (rows.Count > 10000) throw new InvalidDataException("CSV may contain at most 10,000 vehicle pairs.");
            }
            if (rows.Count == 0) throw new InvalidDataException("Add at least one vehicle pair below the headers.");
            string canonical = string.Join(",", Columns) + "\r\n" + string.Join("\r\n", rows.Select(row => string.Join(",", row.Select(value => "\"" + value.Replace("\"", "\"\"") + "\"")))) + "\r\n";
            byte[] content;
            try { content = legacy.GetBytes(canonical); }
            catch (EncoderFallbackException) { throw new InvalidDataException("A character cannot be saved in the existing Windows-1252 CSV format. Review the vehicle names; accents such as Citroen's e with diaeresis are supported."); }
            if (content.Length > MaxBytes) throw new InvalidDataException("The formatted CSV exceeds 2 MB.");
            return new CsvInput(name, rows.ToArray(), expanded, content);
        }
        catch (MalformedLineException error) { throw new InvalidDataException($"Malformed CSV near line {parser.ErrorLineNumber}. Check quotation marks and commas.", error); }
    }
}
