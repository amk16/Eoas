<!-- d0ac492c-98cd-42f1-a645-fd030b3faf0d 34fbf4bc-cd42-4c95-b5db-7f6d39fab0aa -->
# Frontend Code Review & Cleanup Plan

## Overview

This plan addresses 4 core review areas: unused code removal, comment standardization, logging strategy, and code quality improvements.

## 1. Unused Code Removal

### 1.1 Unused Components

- **ChromaGrid.tsx** - Not imported/used anywhere in the codebase - DELETE
- **AudioCapture.tsx** - Not imported/used anywhere - DELETE

### 1.2 Route Issues

- **Home.tsx line 43**: References `/scribe` route but this route doesn't exist in App.tsx
  - Fix: Update Home.tsx to navigate to `/ioun-silence` instead, OR add redirect route
  - Recommendation: Update Home.tsx navigation to `/ioun-silence` since that's the active route

### 1.3 Duplicate/Legacy Components

- **LiveScribe.tsx** vs **LiveScribeSilence.tsx**:
  - `LiveScribe.tsx` is used in `SessionView.tsx`
  - `LiveScribeSilence.tsx` is used in `VoiceAssistant.tsx`
  - Both appear to be actively used, keep both but verify if consolidation is possible

### 1.4 Unused Imports

- Scan all files for unused imports using ESLint rules
- Check for unused variables (especially refs, state variables)
- Review `ProtectedRoute.tsx` - interface formatting issue (empty line 6)

## 2. Comment Standardization

### 2.1 Remove Development Comments

- Remove all TODO/FIXME/HACK comments (or move to issue tracker)
- Remove "Note:" comments about SDK integration that are no longer relevant
- Remove backward compatibility comments that are no longer needed

### 2.2 Create Comment Standards

Create a standardized commenting approach:

- **File-level**: JSDoc-style comments for complex components explaining purpose
- **Function-level**: JSDoc comments for public/exposed functions explaining params, returns, and purpose
- **Complex logic**: Inline comments only for non-obvious business logic
- **Interface/Type comments**: Brief descriptions for complex types

### 2.3 Files Needing Comment Review

- `LiveScribe.tsx` - Remove SDK integration notes
- `LiveScribeSilence.tsx` - Remove SDK integration notes  
- `VoiceAssistant.tsx` - Clean up inline explanatory comments
- `imageGenerationService.ts` - Remove TODO comment
- All service files - Standardize function documentation

## 3. Logging Strategy

### 3.1 Create Logger Utility

Create `src/lib/logger.ts`:

```typescript
// Logger with levels: debug, info, warn, error
// Environment-based: only log in development, or use proper log levels
// Structured logging format
```

### 3.2 Remove Console Logs

- **api.ts** (lines 5-8, 25, 33, 41): Remove request/response logging from interceptors (keep errors only)
- **VoiceAssistant.tsx**: ~50+ console.log statements - convert to logger with appropriate levels
- **SessionView.tsx**: ~15+ console.log statements - convert to logger
- **LiveScribe.tsx**: ~10+ console.log statements - convert to logger  
- **LiveScribeSilence.tsx**: ~10+ console.log statements - convert to logger
- **imageGenerationService.ts**: Multiple console.log/warn/error - convert to logger
- All other components with console statements - convert systematically

### 3.3 Logging Rules

- **Errors**: Always log with logger.error() - keep these
- **Info**: Only for important state changes (conversation created, session started, etc.)
- **Debug**: For detailed flow information (only in development mode)
- **Remove**: Success confirmations, "loaded X items", buffer updates, etc.

## 4. Bad Practices & Quick Fixes

### 4.1 Formatting & Code Quality

- **App.tsx lines 125-129**: Remove empty/whitespace lines
- **ProtectedRoute.tsx line 6**: Fix interface formatting (remove empty line in interface definition)
- Remove unused React imports (e.g., unused `React` type imports)

### 4.2 API Interceptor Improvements

- **api.ts**: 
  - Remove verbose request/response logging (lines 5-8, 25, 33)
  - Keep error logging but make it less verbose
  - Consider removing startup config logs (lines 6-8) or make them debug-only

### 4.3 Error Handling

- Review error handling patterns - some places use `err: any`, consider better typing
- Standardize error message extraction patterns

### 4.4 Code Organization

- Review for duplicate patterns that could be extracted to utilities
- Check for magic numbers/strings that should be constants

## Implementation Order

1. **Phase 1: Remove Unused Code** (ChromaGrid, AudioCapture, fix route)
2. **Phase 2: Create Logger Utility** (Create logger.ts, implement logging strategy)
3. **Phase 3: Replace Console Logs** (Systematically replace all console.* with logger)
4. **Phase 4: Clean Comments** (Remove unnecessary comments, standardize remaining)
5. **Phase 5: Fix Bad Practices** (Formatting, API interceptors, code quality)

## Files to Modify

**Deletions:**

- `src/components/ChromaGrid.tsx`
- `src/components/audio/AudioCapture.tsx`

**Major Changes:**

- `src/services/api.ts` - Remove excessive logging
- `src/components/VoiceAssistant.tsx` - Replace ~50 console logs
- `src/components/sessions/SessionView.tsx` - Replace ~15 console logs
- `src/components/LiveScribe.tsx` - Replace console logs, clean comments
- `src/components/LiveScribeSilence.tsx` - Replace console logs, clean comments
- `src/services/imageGenerationService.ts` - Replace logs, remove TODO

**Minor Changes:**

- `src/App.tsx` - Remove empty lines, fix formatting
- `src/components/Home.tsx` - Fix /scribe route reference
- `src/components/ProtectedRoute.tsx` - Fix interface formatting
- All other components with console statements

**New Files:**

- `src/lib/logger.ts` - Logging utility