<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('crawled_data', function (Blueprint $table) {
            $table->id();
            $table->string('url')->unique();
            $table->longText('content');
            $table->string('title')->nullable();
            $table->json('metadata')->nullable(); // Store extracted metadata as JSON
            $table->timestamp('crawled_at');
            $table->timestamps();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('crawled_data');
    }
};
