<?php
if(!isset($_GET['file']) || !isset($_GET['token'])){
    die("Missing data");
}

$file = $_GET['file'];
$token = $_GET['token'];

$botUrl = "https://YOUR_DOMAIN_NAME/$file";
$api = "https://api.telegram.org/bot$token/setWebhook?url=$botUrl";

$response = file_get_contents($api);

echo "<h2>✅ Bot Live Successfully</h2>";
echo "<p>Webhook URL:</p>";
echo "<code>$botUrl</code>";
echo "<pre>$response</pre>";