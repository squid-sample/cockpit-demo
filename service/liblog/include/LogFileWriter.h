#ifndef __LOG_FILE_WRITER_H__
#define __LOG_FILE_WRITER_H__

#include "LogWriter.h"
#include <string>
#include <fstream>

class LogFileWriter : public LogWriter {
public:
    LogFileWriter(const std::string& filename = "");
    ~LogFileWriter() override;

    bool init() override;
    void write(const LogEntry& entry) override;
    void flush() override;

    void setFilename(const std::string& filename);
    void setMaxFileSize(size_t max_size);
    void setMaxFiles(int max_files);

private:
    bool rotateFile();
    std::string getTimestamp() const;
    
    std::string mFilename;
    std::ofstream mFile;
    size_t mCurrentSize;
    size_t mMaxFileSize;
    int mMaxFiles;
    int mCurrentFileIndex;
};

#endif