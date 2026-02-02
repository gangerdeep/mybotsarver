<?php
if(!isset($_FILES['botfile']) || !isset($_POST['token'])){
    die("Invalid Request");
}

$token = trim($_POST['token']);

if(strlen($token) < 30){
    die("Invalid Bot Token");
}

$uploadDir = "bots/";
if(!is_dir($uploadDir)){
    mkdir($uploadDir);
}

$fileName = basename($_FILES["botfile"]["name"]);
$targetFile = $uploadDir . time() . "_" . $fileName;

if(pathinfo($targetFile, PATHINFO_EXTENSION) != "php"){
    die("Only PHP files allowed");
}

if(move_uploaded_file($_FILES["botfile"]["tmp_name"], $targetFile)){
    header("Location: setwebhook.php?file=$targetFile&token=$token");
} else {
    echo "Upload Failed";
}