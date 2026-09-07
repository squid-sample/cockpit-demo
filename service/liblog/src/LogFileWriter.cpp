#include "LogFileWriter.h"
#include "LogCommon.h"
#include <cstdio>
#include <cstring>
#include <sys/stat.h>
#include <time.h>

LogFileWriter::LogFileWriter(const std::string& filename) 
    : mFilename(filename), mCurrentSize(0), mMaxFileSize(1024 * 1024 * 10),
      mMaxFiles(5), mCurrentFileIndex(0) {
    mLevel = LOG_LEVEL_INFO;
}

LogFileWriter::~LogFileWriter() {
    if (mFile.is_open()) {
        mFile.close();
    }
}

bool LogFileWriter::init() {
    if (mFilename.empty()) {
        mFilename = "log/service.log";
    }

    size_t pos = mFilename.find_last_of("/\\");
    if (pos != std::string::npos) {
        std::string dir = mFilename.substr(0, pos);
#ifdef _WIN32
        mkdir(dir.c_str());
#else
        mkdir(dir.c_str(), 0755);
#endif
    }

    mFile.open(mFilename, std::ios::out | std::ios::app);
    if (!mFile.is_open()) {
        return false;
    }

    return true;
}

void LogFileWriter::write(const LogEntry& entry) {
    if (!mFile.is_open()) {
        return;
    }

    std::string line = getTimestamp();
    line += " [";
    line += log_level_to_string(entry.level);
    line += "] [";
    line += entry.module;
    line += "] [P:";
    line += std::to_string(entry.pid);
    line += " T:";
    line += std::to_string(entry.tid);
    line += "] [";
    line += entry.file;
    line += ":";
    line += std::to_string(entry.line);
    line += ":";
    line += entry.func;
    line += "] ";
    line += entry.message;
    line += "\n";

    mFile << line;
    mCurrentSize += line.size();

    if (mCurrentSize >= mMaxFileSize) {
        rotateFile();
    }
}

void LogFileWriter::flush() {
    if (mFile.is_open()) {
        mFile.flush();
    }
}

void LogFileWriter::setFilename(const std::string& filename) {
    mFilename = filename;
}

void LogFileWriter::setMaxFileSize(size_t max_size) {
    mMaxFileSize = max_size;
}

void LogFileWriter::setMaxFiles(int max_files) {
    mMaxFiles = max_files;
}

bool LogFileWriter::rotateFile() {
    if (mFile.is_open()) {
        mFile.close();
    }

    for (int i = mMaxFiles - 1; i > 0; --i) {
        std::string old_name = mFilename + "." + std::to_string(i - 1);
        std::string new_name = mFilename + "." + std::to_string(i);
        
#ifdef _WIN32
        remove(new_name.c_str());
        rename(new_name.c_str(), new_name.c_str());
#else
        rename(old_name.c_str(), new_name.c_str());
#endif
    }

    std::string backup_name = mFilename + ".0";
#ifdef _WIN32
    remove(backup_name.c_str());
    rename(mFilename.c_str(), backup_name.c_str());
#else
    rename(mFilename.c_str(), backup_name.c_str());
#endif

    mFile.open(mFilename, std::ios::out);
    if (!mFile.is_open()) {
        return false;
    }

    mCurrentSize = 0;
    return true;
}

std::string LogFileWriter::getTimestamp() const {
    time_t t = time(nullptr);
    struct tm* tm_info = localtime(&t);
    char time_str[32];
    strftime(time_str, sizeof(time_str), "%Y-%m-%d %H:%M:%S", tm_info);
    return std::string(time_str);
}