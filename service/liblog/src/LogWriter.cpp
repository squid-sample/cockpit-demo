#include "LogWriter.h"

void LogWriter::setLevel(LogLevel level) {
    mLevel = level;
}

LogLevel LogWriter::getLevel() const {
    return mLevel;
}

bool LogWriter::shouldWrite(LogLevel level) const {
    return level >= mLevel;
}