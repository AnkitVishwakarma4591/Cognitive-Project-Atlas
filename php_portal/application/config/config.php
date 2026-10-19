<?php
defined('BASEPATH') OR exit('No direct script access allowed');

/*
|--------------------------------------------------------------------------
| Base Site URL
|--------------------------------------------------------------------------
*/
$config['base_url'] = getenv('CI_BASE_URL') ?: 'http://localhost:8080/';

/*
|--------------------------------------------------------------------------
| Index File
|--------------------------------------------------------------------------
*/
$config['index_page'] = '';

/*
|--------------------------------------------------------------------------
| URI PROTOCOL
|--------------------------------------------------------------------------
*/
$config['uri_protocol'] = 'REQUEST_URI';

/*
|--------------------------------------------------------------------------
| Security & CSRF Protection (PDF Requirement)
|--------------------------------------------------------------------------
*/
$config['csrf_protection'] = TRUE;
$config['csrf_token_name'] = 'atlas_csrf_token';
$config['csrf_cookie_name'] = 'atlas_csrf_cookie';
$config['csrf_expire'] = 7200;
$config['csrf_regenerate'] = FALSE; // Keep consistent across AJAX chat turns
$config['csrf_exclude_uris'] = array('api/*');

/*
|--------------------------------------------------------------------------
| Encryption Key
|--------------------------------------------------------------------------
*/
$config['encryption_key'] = 'ProjectAtlas_CodeIgniter3_SecureKey_2025';

/*
|--------------------------------------------------------------------------
| Session & Logging
|--------------------------------------------------------------------------
*/
$config['sess_driver'] = 'files';
$config['sess_cookie_name'] = 'atlas_session';
$config['sess_expiration'] = 7200;
$config['sess_save_path'] = sys_get_temp_dir();
$config['sess_match_ip'] = FALSE;
$config['sess_time_to_update'] = 300;

$config['log_threshold'] = 1;
$config['log_path'] = '';
$config['log_file_extension'] = '';
$config['log_file_permissions'] = 0644;
$config['log_date_format'] = 'Y-m-d H:i:s';

/*
|--------------------------------------------------------------------------
| Python API Service Endpoint Configuration
|--------------------------------------------------------------------------
*/
$config['atlas_api_url'] = getenv('ATLAS_API_URL') ?: 'http://api:8000';
$config['atlas_api_key'] = getenv('ATLAS_API_KEY') ?: 'atlas-secret-key-2025';
$config['atlas_request_timeout'] = 30; // 30 seconds per requirement
