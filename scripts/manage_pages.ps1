Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public class CredManager {
    [DllImport("advapi32.dll", EntryPoint = "CredReadW", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern bool CredRead(string target, int type, int reservedFlag, out IntPtr credentialPtr);

    [DllImport("advapi32.dll", EntryPoint = "CredFree", SetLastError = true)]
    public static extern void CredFree(IntPtr credential);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct CREDENTIAL {
        public int Flags;
        public int Type;
        public string TargetName;
        public string Comment;
        public long LastWritten;
        public int CredentialBlobSize;
        public IntPtr CredentialBlob;
        public int Persist;
        public int AttributeCount;
        public IntPtr Attributes;
        public string TargetAlias;
        public string UserName;
    }

    public static string GetPassword(string target) {
        IntPtr credPtr;
        if (CredRead(target, 1, 0, out credPtr)) {
            var cred = (CREDENTIAL)Marshal.PtrToStructure(credPtr, typeof(CREDENTIAL));
            byte[] bytes = new byte[cred.CredentialBlobSize];
            Marshal.Copy(cred.CredentialBlob, bytes, 0, cred.CredentialBlobSize);
            CredFree(credPtr);
            return Encoding.Unicode.GetString(bytes);
        }
        return null;
    }
}
"@

$token = [CredManager]::GetPassword("git:https://Bhuvan-Reddy-07@github.com")
if (-not $token) {
    Write-Error "Could not retrieve token from Windows Credential Manager"
    exit 1
}

$headers = @{
    "Authorization" = "Bearer $token"
    "Accept" = "application/vnd.github.v3+json"
    "User-Agent" = "HealthSupply-Pages-Deployer"
    "X-GitHub-Api-Version" = "2022-11-28"
}

Write-Output "Checking GitHub Pages status..."
try {
    $res = Invoke-RestMethod -Uri "https://api.github.com/repos/Bhuvan-Reddy-07/healthsupply/pages" -Headers $headers -Method Get
    Write-Output "Pages already enabled:"
    $res | ConvertTo-Json -Depth 5
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Output "Pages query status code: $statusCode"
    if ($statusCode -eq 404) {
        Write-Output "Pages is not yet enabled. Enabling GitHub Pages with source 'gh-pages' branch..."
        $body = @{
            source = @{
                branch = "gh-pages"
                path = "/"
            }
        } | ConvertTo-Json

        try {
            $enableRes = Invoke-RestMethod -Uri "https://api.github.com/repos/Bhuvan-Reddy-07/healthsupply/pages" -Headers $headers -Method Post -Body $body -ContentType "application/json"
            Write-Output "GitHub Pages enabled successfully!"
            $enableRes | ConvertTo-Json -Depth 5
        } catch {
            Write-Output "Failed to enable via POST: $($_.Exception.Message)"
            if ($_.ErrorDetails) {
                Write-Output "Error details: $($_.ErrorDetails.Message)"
            }
        }
    } else {
        Write-Output "Error: $($_.Exception.Message)"
        if ($_.ErrorDetails) {
            Write-Output "Error details: $($_.ErrorDetails.Message)"
        }
    }
}
