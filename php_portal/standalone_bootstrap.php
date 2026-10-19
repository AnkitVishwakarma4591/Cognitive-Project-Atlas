<?php
/**
 * Standalone CodeIgniter 3 Compatible Micro-Kernel
 * Enables immediate execution of Chat.php, Atlas_client.php, and chat_view.php
 * under PHP built-in server or Apache without external Composer downloads.
 */

if (!defined('BASEPATH')) define('BASEPATH', __DIR__ . '/');
if (!defined('APPPATH')) define('APPPATH', __DIR__ . '/application/');
if (!defined('VIEWPATH')) define('VIEWPATH', __DIR__ . '/application/views/');

session_start();

function &get_instance() {
    return CI_Controller::get_instance();
}

function site_url($uri = '') {
    return '/' . ltrim($uri, '/');
}

function redirect($uri = '') {
    header('Location: ' . site_url($uri));
    exit;
}

function log_message($level, $msg) {
    error_log("[CI3 $level] $msg");
}

class CI_Input {
    public function post($key = NULL, $xss_clean = FALSE) {
        if ($key === NULL) return $_POST;
        return isset($_POST[$key]) ? $_POST[$key] : NULL;
    }
    public function method() {
        return strtolower($_SERVER['REQUEST_METHOD'] ?? 'get');
    }
    public function is_ajax_request() {
        return (!empty($_SERVER['HTTP_X_REQUESTED_WITH']) && strtolower($_SERVER['HTTP_X_REQUESTED_WITH']) === 'xmlhttprequest');
    }
}

class CI_Output {
    protected $body = '';
    protected $content_type = 'text/html';
    public function set_content_type($type) {
        $this->content_type = $type;
        header("Content-Type: $type; charset=UTF-8");
        return $this;
    }
    public function set_output($output) {
        $this->body = $output;
        echo $this->body;
        return $this;
    }
}

class CI_Security {
    public function get_csrf_token_name() {
        return 'atlas_csrf_token';
    }
    public function get_csrf_hash() {
        if (empty($_SESSION['atlas_csrf_token'])) {
            $_SESSION['atlas_csrf_token'] = bin2hex(random_bytes(16));
        }
        return $_SESSION['atlas_csrf_token'];
    }
}

class CI_Session {
    public $session_id;
    public function __construct() {
        $this->session_id = session_id();
    }
    public function userdata($key) {
        return $_SESSION[$key] ?? NULL;
    }
    public function set_userdata($key, $val) {
        $_SESSION[$key] = $val;
    }
}

class CI_Loader {
    public function library($lib) {
        $name = strtolower($lib);
        $ci =& get_instance();
        if ($name === 'session') {
            $ci->session = new CI_Session();
        } elseif ($name === 'atlas_client') {
            require_once APPPATH . 'libraries/Atlas_client.php';
            $ci->atlas_client = new Atlas_client();
        }
    }
    public function helper($h) {}
    public function config($c) {}
    public function database($d = '', $return = FALSE, $active_record = TRUE) {}
    public function view($view, $vars = array()) {
        extract($vars);
        include VIEWPATH . $view . '.php';
    }
}

class CI_Config {
    public function item($key) {
        global $config;
        if (!isset($config)) {
            include APPPATH . 'config/config.php';
        }
        return $config[$key] ?? NULL;
    }
}

class CI_Controller {
    private static $instance;
    public $load;
    public $input;
    public $output;
    public $security;
    public $session;
    public $atlas_client;
    public $config;

    public function __construct() {
        self::$instance =& $this;
        $this->load = new CI_Loader();
        $this->input = new CI_Input();
        $this->output = new CI_Output();
        $this->security = new CI_Security();
        $this->config = new CI_Config();
    }

    public static function &get_instance() {
        return self::$instance;
    }
}

// Router dispatcher
$uri = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
$uri = trim($uri, '/');

require_once APPPATH . 'controllers/Chat.php';
$controller = new Chat();

if ($uri === 'chat/send') {
    $controller->send();
} elseif ($uri === 'chat/feedback') {
    $controller->feedback();
} elseif ($uri === 'chat/switch_client') {
    $controller->switch_client();
} else {
    $controller->index();
}
