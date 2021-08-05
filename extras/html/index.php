<?php
# This file is part of photoframe (https://github.com/mrworf/photoframe).
#
# photoframe is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# photoframe is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with photoframe.  If not, see <http://www.gnu.org/licenses/>.
#

$headers = getallheaders();
if (!isset($headers["X-Real-IP"]) && !isset($headers["x-forwarded-for"])) {
	die("No IP provided");
}
$ip = $headers["X-Real-IP"];
if ($ip == "")
	$ip = $headers["x-forwarded-for"];

// Connect to memcache
$mem = new Memcache;
$mem->addServer("127.0.0.1", 11211);

if (isset($_GET["register"])) {
	header("Content-Type: text/plain");
	$id = MD5(uniqid(rand(), TRUE));
	$mem->set($id, $id, 0, 600); // It lives for 10min
	print($id);
} else if (isset($_GET["state"]) && strlen($_GET["state"]) > 1) {
	$params = explode("-", $_GET["state"]);
	if (count($params) < 2) {
		http_response_code(404);
		die("No such redirect 1");
	}
	if ($mem->get($params[0]) !== $params[0]) {
		http_response_code(404);
		die("No such redirect");
	}
	// We only allow redirects to private IPs
	$parts = explode(":", $params[1]);
	if (count($parts) > 2) {
		http_response_code(404);
		die("Invalid IP");
	} else if (count($parts) == 2) {
		$port = intval($parts[1]);
		if ($port != 80 && $port < 1024) {
			// Only port 80 is allowed when using priviliged ports
			http_response_code(404);
			die("Invalid port");
		}
	} else {
		$port = 7777; // Legacy support
	}
	$dest = explode(".", $parts[0]);
	if (count($dest) == 4) {
		// Filter bad apples
		for ($i = 0; $i != 4; ++$i) {
			$dest[$i] = intval($dest[$i]);
			if ($dest[$i] < 0 || $dest[$i] > 255) {
				http_response_code(404);
				die("Invalid IP");
			}
		}
		if ($dest[0] == 10)
			$valid = TRUE;
		else if ($dest[0] == 172 && $dest[1] > 15 && dest[1] < 32)
			$valid = TRUE;
		else if ($dest[0] == 192 && $dest[1] == 168)
			$valid = TRUE;
		else if ($dest[0] == 169 && $dest[1] == 254)
			$valid = TRUE;
		else
			$valid = FALSE;
		if ($valid)
			header(sprintf("Location: http://%d.%d.%d.%d:%d/callback?state=%s&code=%s",
			$dest[0], $dest[1], $dest[2], $dest[3], $port,
			$_GET["state"],
			$_GET["code"]
			));
			die();
	}
	http_response_code(404);
	die("No such redirect");
} else {
	header("Location: https://github.com/mrworf/photoframe#photoframe");
	die();
}
