##  60 students - 30 pairs - working on clusters
##  1 Storage Account | Folder with permissions for pairs 
##  Every group has permissions for a folder - once for semester - Students mail existing users | Group must be created - "firstlast-firstlast"
##  1 Create NEW Storage account
##  Deletion of groups - another script - output gorpus names to file to run later after semester ends.
##  Folder is name of the group  

$resourceGroupName = "Technion"
$coursestorageaccount = "dacoursestg100"
New-Item .\groups.txt -Force

Connect-AzAccount
Connect-MgGraph

## Deploy the SA from templates
New-AzResourceGroupDeployment -ResourceGroupName $resourceGroupName -TemplateFile ./template.json -TemplateParameterFile ./parameters.json -storageAccountName $coursestorageaccount

## Assign Blob Data Owner to RG ##
New-AzRoleAssignment -ObjectId (Get-AzADUser -DisplayName "User running the Script").id `
-RoleDefinitionName "Storage Blob Data Contributor" `
-ResourceGroupName $resourceGroupName

$ctx = New-AzStorageContext -StorageAccountName $coursestorageaccount -UseConnectedAccount
$students = Import-Csv .\students.csv -Header student1,student2,student3
foreach ($row in $students)
{        
  
    $stud1 = Get-MgUser -UserId $row[0].student1
    $stud2 = Get-MgUser -UserId $row[0].student2
    
    if ($row[0].student3 -notlike ""){
    $stud3 = Get-MgUser -UserId $row[0].student3
    $groupname =  $stud1.GivenName + $stud1.Surname + "-" + $stud2.GivenName + $stud2.Surname + "-" + $stud3.GivenName + $stud3.Surname
    New-MgGroup -DisplayName $groupname -MailEnabled:$False -MailNickname $groupname -SecurityEnabled
    $groupid = Get-MgGroup -All | Where-Object {$_.DisplayName -like $groupname}
    New-MgGroupMember -GroupId $groupid.Id -DirectoryObjectId $stud1.Id
    New-MgGroupMember -GroupId $groupid.Id -DirectoryObjectId $stud2.Id
    New-MgGroupMember -GroupId $groupid.Id -DirectoryObjectId $stud3.Id
    
    New-AzStorageContainer -Context $ctx -Name $groupname.ToLower()
    $filesystemName = $groupname.ToLower()  
    $acl = (Get-AzDataLakeGen2Item -Context $ctx -FileSystem $filesystemName).ACL
    $acl = set-AzDataLakeGen2ItemAclObject -AccessControlType Group -EntityId $groupid.id -Permission rwx -InputObject $acl
    Update-AzDataLakeGen2AclRecursive -Context $ctx -FileSystem $filesystemName -Acl $acl
    Add-Content -Path .\groups.txt -Value $groupname

}
    else 
    {
    $groupname =  $stud1.GivenName + $stud1.Surname + "-" + $stud2.GivenName + $stud2.Surname
    New-MgGroup -DisplayName $groupname -MailEnabled:$False -MailNickname $groupname -SecurityEnabled
    $groupid = Get-MgGroup -All | Where-Object {$_.DisplayName -like $groupname}
    New-MgGroupMember -GroupId $groupid.Id -DirectoryObjectId $stud1.Id
    New-MgGroupMember -GroupId $groupid.Id -DirectoryObjectId $stud2.Id 
    
    New-AzStorageContainer -Context $ctx -Name $groupname.ToLower()
    $filesystemName = $groupname.ToLower()  
    $acl = (Get-AzDataLakeGen2Item -Context $ctx -FileSystem $filesystemName).ACL
    $acl = set-AzDataLakeGen2ItemAclObject -AccessControlType Group -EntityId $groupid.id -Permission rwx -InputObject $acl
    Update-AzDataLakeGen2AclRecursive -Context $ctx -FileSystem $filesystemName -Acl $acl
    Add-Content -Path .\groups.txt -Value $groupname

    }

}


## only required for automation / SA access to templates.
#$templatestorageaccount = "tzkstorage"
#$templatestorageRG = "STORAGE-GENERAL"
#$context = (Get-AzStorageAccount -ResourceGroupName $templatestorageRG -AccountName $templatestorageaccount).context
#$sasToken = New-AzStorageAccountSASToken -Context $context -Service blob -ResourceType Service,Container,Object -Permission r -ExpiryTime (Get-Date).AddMinutes(60)
#invoke-webrequest "https://tzkstorage.blob.core.windows.net/template.json"+?$sasToken -outfile $env:temp\template.json
#invoke-webrequest "https://tzkstorage.blob.core.windows.net/parameters.json"?$sasToken -outfile $env:temp\parameters.json
#New-AzResourceGroupDeployment -ResourceGroupName $resourceGroupName -TemplateFile $storageaccount+"/template.json" -TemplateParameterUri $storageaccount+"/parameters.json" #-inline
