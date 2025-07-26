<?php

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use App\Http\Controllers\CrawlerController;

Route::post('/submit-crawl', [CrawlerController::class, 'submitCrawlTask']);
Route::get('/crawl-status/{task_id}', [CrawlerController::class, 'getCrawlStatus']);

