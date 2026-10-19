<?php
defined('BASEPATH') OR exit('No direct script access allowed');

/**
 * Chat Controller
 * 
 * Serves the syndicated research portal copilot interface.
 * Handles chat submission via AJAX, stores conversations & ratings in MySQL,
 * and maintains client session context (C-01 vs C-02).
 */
class Chat extends CI_Controller {

    public function __construct() {
        parent::__construct();
        $this->load->library('session');
        $this->load->library('atlas_client');
        $this->load->helper(array('url', 'security', 'form'));
        
        // Optional database loading
        if (file_exists(APPPATH . 'config/database.php')) {
            $this->load->database('', FALSE, TRUE); // connect if configured
        }

        // Initialize active client session (default C-01 Northwind Utilities)
        if (!$this->session->userdata('active_client_id')) {
            $this->session->set_userdata('active_client_id', 'C-01');
            $this->session->set_userdata('active_company', 'Northwind Utilities');
        }
    }

    /**
     * Index page: Displays interactive copilot chat view.
     */
    public function index() {
        $client_id = $this->session->userdata('active_client_id');
        $company = $this->session->userdata('active_company');
        
        $history = array();
        // Load recent conversations from MySQL if DB is connected
        if (isset($this->db) && $this->db->conn_id) {
            $this->db->where('client_id', $client_id);
            $this->db->order_by('id', 'ASC');
            $this->db->limit(30);
            $query = $this->db->get('conversations');
            if ($query) {
                $history = $query->result_array();
            }
        }

        $data = array(
            'active_client_id' => $client_id,
            'active_company'   => $company,
            'history'          => $history,
            'csrf_token_name'  => $this->security->get_csrf_token_name(),
            'csrf_hash'        => $this->security->get_csrf_hash()
        );

        $this->load->view('chat_view', $data);
    }

    /**
     * Switch client context between C-01 and C-02 for demonstration testing.
     */
    public function switch_client() {
        $target_client = $this->input->post('client_id', TRUE);
        if ($target_client === 'C-02') {
            $this->session->set_userdata('active_client_id', 'C-02');
            $this->session->set_userdata('active_company', 'Blue Delta Infra');
        } else {
            $this->session->set_userdata('active_client_id', 'C-01');
            $this->session->set_userdata('active_company', 'Northwind Utilities');
        }
        redirect('chat');
    }

    /**
     * AJAX endpoint: Processes chat question, invokes Python API, and stores in MySQL.
     */
    public function send() {
        // Enforce JSON POST
        if (!$this->input->is_ajax_request() && $this->input->method() !== 'post') {
            show_error('Direct access not allowed', 400);
            return;
        }

        $question = trim($this->input->post('question', TRUE));
        if (empty($question)) {
            $this->output
                ->set_content_type('application/json')
                ->set_output(json_encode(array('error' => 'Question cannot be blank.')));
            return;
        }

        $client_id = $this->session->userdata('active_client_id') ?: 'C-01';
        $session_id = $this->session->session_id ?: uniqid('sess_', true);

        // Call Python FastAPI service via Atlas_client library
        $response = $this->atlas_client->ask($client_id, $question, $session_id);

        $conversation_id = null;
        // Verify or store conversation in MySQL
        if (isset($this->db) && $this->db->conn_id) {
            $insert_data = array(
                'session_id'     => $session_id,
                'client_id'      => $client_id,
                'question'       => $question,
                'answer'         => isset($response['answer']) ? $response['answer'] : '',
                'citations'      => isset($response['citations']) ? json_encode($response['citations']) : '[]',
                'conflicts'      => isset($response['conflicts']) ? json_encode($response['conflicts']) : '[]',
                'derived_values' => isset($response['derived_values']) ? json_encode($response['derived_values']) : '[]',
                'confidence'     => isset($response['confidence']) ? (float)$response['confidence'] : 0.0,
                'escalated'      => (!empty($response['escalated'])) ? 1 : 0
            );
            $this->db->insert('conversations', $insert_data);
            $conversation_id = $this->db->insert_id();
        }

        $response['conversation_id'] = $conversation_id;
        $response['csrf_hash'] = $this->security->get_csrf_hash();

        $this->output
            ->set_content_type('application/json')
            ->set_output(json_encode($response));
    }

    /**
     * AJAX endpoint: Submits thumbs up / thumbs down feedback.
     */
    public function feedback() {
        $conversation_id = $this->input->post('conversation_id', TRUE);
        $rating = $this->input->post('rating', TRUE);
        $comments = $this->input->post('comments', TRUE);

        if (!in_array($rating, array('up', 'down'))) {
            $this->output
                ->set_content_type('application/json')
                ->set_output(json_encode(array('success' => false, 'error' => 'Invalid rating.')));
            return;
        }

        // Store in MySQL feedback table
        if (isset($this->db) && $this->db->conn_id && $conversation_id) {
            $this->db->insert('feedback', array(
                'conversation_id' => (int)$conversation_id,
                'rating'          => $rating,
                'comments'        => $comments
            ));
        }

        // Also notify Python API
        if ($conversation_id) {
            $this->atlas_client->submit_feedback($conversation_id, $rating, $comments);
        }

        $this->output
            ->set_content_type('application/json')
            ->set_output(json_encode(array(
                'success'   => true,
                'csrf_hash' => $this->security->get_csrf_hash()
            )));
    }
}
