<?php
defined('BASEPATH') OR exit('No direct script access allowed');

/**
 * Atlas_client Library
 * 
 * Communicates with the Project Atlas FastAPI backend service.
 * Enforces timeout boundaries, API key authentication, and provides
 * robust graceful fallback error responses on failure.
 */
class Atlas_client {

    protected $ci;
    protected $api_url;
    protected $api_key;
    protected $timeout;

    public function __construct() {
        $this->ci =& get_instance();
        $this->ci->load->config('config');
        
        $this->api_url = rtrim($this->ci->config->item('atlas_api_url'), '/');
        $this->api_key = $this->ci->config->item('atlas_api_key');
        $this->timeout = $this->ci->config->item('atlas_request_timeout') ?: 30;
    }

    /**
     * Sends user inquiry to Python FastAPI Copilot.
     * 
     * @param string $client_id
     * @param string $question
     * @param string|null $session_id
     * @return array Standardized copilot response array
     */
    public function ask($client_id, $question, $session_id = null) {
        $endpoint = $this->api_url . '/chat';
        $payload = json_encode(array(
            'client_id'  => $client_id,
            'question'   => $question,
            'session_id' => $session_id
        ));

        $ch = curl_init($endpoint);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);
        curl_setopt($ch, CURLOPT_TIMEOUT, $this->timeout);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 5);
        curl_setopt($ch, CURLOPT_HTTPHEADER, array(
            'Content-Type: application/json',
            'X-API-Key: ' . $this->api_key,
            'Content-Length: ' . strlen($payload)
        ));

        $response_body = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $curl_error = curl_error($ch);
        $curl_errno = curl_errno($ch);
        curl_close($ch);

        // Handle Curl Timeout / Connection Failures Gracefully
        if ($curl_errno !== 0) {
            log_message('error', "Atlas_client CURL Error ({$curl_errno}): {$curl_error}");
            return $this->fallback_response(
                "Our analytical AI copilot is currently experiencing connectivity latency or a timeout. " .
                "Your inquiry has been received, but an immediate response could not be generated. " .
                "A human research analyst has been alerted and will follow up shortly.",
                0.20,
                true
            );
        }

        if ($http_code !== 200) {
            log_message('error', "Atlas_client HTTP {$http_code}: {$response_body}");
            return $this->fallback_response(
                "The Report Copilot service returned an unexpected operational status (HTTP {$http_code}). " .
                "Please refresh the portal or reach out to your CMR account manager if this persists.",
                0.30,
                true
            );
        }

        $decoded = json_decode($response_body, true);
        if (json_last_error() !== JSON_ERROR_NONE || !is_array($decoded)) {
            log_message('error', "Atlas_client Invalid JSON: {$response_body}");
            return $this->fallback_response(
                "Received an invalid data stream from the analytics engine. Fallback engaged.",
                0.30,
                true
            );
        }

        return $decoded;
    }

    /**
     * Submits thumbs-up / thumbs-down user feedback to Python API backend.
     */
    public function submit_feedback($conversation_id, $rating, $comments = null) {
        $endpoint = $this->api_url . '/feedback';
        $payload = json_encode(array(
            'conversation_id' => (int)$conversation_id,
            'rating'          => $rating,
            'comments'        => $comments
        ));

        $ch = curl_init($endpoint);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);
        curl_setopt($ch, CURLOPT_TIMEOUT, 5);
        curl_setopt($ch, CURLOPT_HTTPHEADER, array(
            'Content-Type: application/json',
            'X-API-Key: ' . $this->api_key
        ));
        $res = curl_exec($ch);
        curl_close($ch);
        return $res;
    }

    /**
     * Fallback response generator satisfying PDF graceful degradation requirements.
     */
    protected function fallback_response($message, $confidence = 0.25, $escalated = true) {
        return array(
            'answer'         => $message,
            'citations'      => array(),
            'confidence'     => $confidence,
            'conflicts'      => array(),
            'derived_values' => array(),
            'escalated'      => $escalated,
            'metadata'       => array(
                'status'    => 'fallback_degraded',
                'timestamp' => gmdate('Y-m-d\TH:i:s\Z')
            )
        );
    }
}
