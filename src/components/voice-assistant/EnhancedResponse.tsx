import { memo, useMemo } from 'react';
import { Streamdown } from 'streamdown';
import type { ComponentProps } from 'react';
import { StructuredDataRenderer } from './StructuredDataRenderer';
import { CharacterDetailView } from './CharacterDetailView';
import { SessionDetailView } from './SessionDetailView';
import { CampaignDetailView } from './CampaignDetailView';
import { cn } from '@/lib/utils';

type EnhancedResponseProps = ComponentProps<typeof Streamdown>;

export const EnhancedResponse = memo(({ className, components, ...props }: EnhancedResponseProps) => {
  // Phase 3: Custom code block renderer for structured data
  const customComponents = useMemo(() => {
    // Helper to extract language and code from code block structure
    const extractCodeBlockInfo = (children: any): { language: string; code: string } | null => {
      if (!children) return null;
      
      // Handle React element
      if (children.props) {
        const className = children.props.className || '';
        
        // Debug: log what we're seeing
        console.log('[EnhancedResponse] Extracting code block info:', {
          className,
          props: Object.keys(children.props),
          childrenType: typeof children.props.children
        });
        
        // Try multiple patterns to match language
        // Pattern 1: language-markdown:character-detail (with colon)
        let match = /language-([\w:-]+)/.exec(className);
        if (!match) {
          // Pattern 2: language-markdown (without colon, might be split)
          match = /language-(\w+)/.exec(className);
        }
        
        if (match) {
          let language = match[1];
          
          // Check for data-language or other attributes that might contain the full language spec
          if (children.props['data-language']) {
            language = children.props['data-language'];
          }
          
          // Extract code content - handle different child structures
          let codeString = '';
          if (typeof children.props.children === 'string') {
            codeString = children.props.children;
          } else if (Array.isArray(children.props.children)) {
            codeString = children.props.children
              .map((child: any) => {
                if (typeof child === 'string') return child;
                if (child?.props?.children) return String(child.props.children);
                return '';
              })
              .join('');
          } else if (children.props.children?.props?.children) {
            codeString = String(children.props.children.props.children);
          } else {
            codeString = String(children.props.children || '');
          }
          
          codeString = codeString.replace(/\n$/, '');
          
          console.log('[EnhancedResponse] Extracted:', { language, codeLength: codeString.length });
          
          return { language, code: codeString };
        }
      }
      
      // Handle array of children (code block might have nested structure)
      if (Array.isArray(children)) {
        for (const child of children) {
          const result = extractCodeBlockInfo(child);
          if (result) return result;
        }
      }
      
      return null;
    };

    return {
      pre: ({ children, ...props }: any) => {
        const codeInfo = extractCodeBlockInfo(children);
        
        // Debug logging (can be removed in production)
        if (codeInfo) {
          console.log('[EnhancedResponse] Code block detected:', {
            language: codeInfo.language,
            codeLength: codeInfo.code.length,
            codePreview: codeInfo.code.substring(0, 100)
          });
        }
        
        if (!codeInfo) {
          // Default pre block rendering for regular code blocks
          return (
            <pre className={cn("overflow-x-auto rounded-lg bg-neutral-900 p-4 my-4", props.className)} {...props}>
              {children}
            </pre>
          );
        }
        
        // Check if this is a structured data code block (JSON)
        if (codeInfo.language.startsWith('json:character') || 
            codeInfo.language === 'json:characters' ||
            codeInfo.language.startsWith('json:session') || 
            codeInfo.language === 'json:sessions' ||
            codeInfo.language.startsWith('json:campaign')) {
          // Render structured data component directly
          return (
            <StructuredDataRenderer language={codeInfo.language} code={codeInfo.code} />
          );
        }
        
        // Check if this is a markdown detail view (exact match and case-insensitive)
        const normalizedLang = codeInfo.language.toLowerCase().trim();
        if (normalizedLang === 'markdown:character-detail') {
          console.log('[EnhancedResponse] Rendering CharacterDetailView');
          return (
            <CharacterDetailView content={codeInfo.code} />
          );
        }
        
        if (normalizedLang === 'markdown:session-detail') {
          console.log('[EnhancedResponse] Rendering SessionDetailView');
          return (
            <SessionDetailView content={codeInfo.code} />
          );
        }
        
        if (normalizedLang === 'markdown:campaign-detail') {
          console.log('[EnhancedResponse] Rendering CampaignDetailView');
          return (
            <CampaignDetailView content={codeInfo.code} />
          );
        }

        // Default pre block rendering for regular code blocks
        return (
          <pre className={cn("overflow-x-auto rounded-lg bg-neutral-900 p-4 my-4", props.className)} {...props}>
            {children}
          </pre>
        );
      },
      code: ({ className, children, ...props }: any) => {
        // Only handle inline code here, block code is handled by pre
        if (className && className.includes('language-')) {
          // This is a code block, let pre handle it
          return (
            <code className={className} {...props}>
              {children}
            </code>
          );
        }
        
        // Inline code
        return (
          <code className={cn("text-sm bg-neutral-900 px-1 py-0.5 rounded", className)} {...props}>
            {children}
          </code>
        );
      },
      // Table components with dark mode support
      table: ({ children, ...props }: any) => {
        return (
          <div className="my-4 overflow-x-auto">
            <table className={cn(
              "w-full border-collapse border border-neutral-700 rounded-lg overflow-hidden",
              props.className
            )} {...props}>
              {children}
            </table>
          </div>
        );
      },
      thead: ({ children, ...props }: any) => {
        return (
          <thead className={cn("bg-neutral-800", props.className)} {...props}>
            {children}
          </thead>
        );
      },
      tbody: ({ children, ...props }: any) => {
        return (
          <tbody className={cn("bg-neutral-900/50", props.className)} {...props}>
            {children}
          </tbody>
        );
      },
      tr: ({ children, ...props }: any) => {
        return (
          <tr className={cn(
            "border-b border-neutral-700 hover:bg-neutral-800/50 transition-colors",
            props.className
          )} {...props}>
            {children}
          </tr>
        );
      },
      th: ({ children, ...props }: any) => {
        return (
          <th className={cn(
            "px-4 py-3 text-left text-sm font-semibold text-neutral-200 border-r border-neutral-700 last:border-r-0",
            props.className
          )} {...props}>
            {children}
          </th>
        );
      },
      td: ({ children, ...props }: any) => {
        return (
          <td className={cn(
            "px-4 py-3 text-sm text-neutral-300 border-r border-neutral-700 last:border-r-0",
            props.className
          )} {...props}>
            {children}
          </td>
        );
      },
      // Enhanced list styling
      ul: ({ children, ...props }: any) => {
        return (
          <ul className={cn(
            "my-3 ml-6 list-disc space-y-1 text-neutral-300",
            props.className
          )} {...props}>
            {children}
          </ul>
        );
      },
      ol: ({ children, ...props }: any) => {
        return (
          <ol className={cn(
            "my-3 ml-6 list-decimal space-y-1 text-neutral-300",
            props.className
          )} {...props}>
            {children}
          </ol>
        );
      },
      li: ({ children, ...props }: any) => {
        return (
          <li className={cn(
            "pl-2 leading-relaxed",
            props.className
          )} {...props}>
            {children}
          </li>
        );
      },
      // Definition lists for stats/attributes
      dl: ({ children, ...props }: any) => {
        return (
          <dl className={cn(
            "my-3 space-y-2",
            props.className
          )} {...props}>
            {children}
          </dl>
        );
      },
      dt: ({ children, ...props }: any) => {
        return (
          <dt className={cn(
            "text-sm font-semibold text-neutral-200",
            props.className
          )} {...props}>
            {children}
          </dt>
        );
      },
      dd: ({ children, ...props }: any) => {
        return (
          <dd className={cn(
            "ml-4 text-sm text-neutral-300 mb-2",
            props.className
          )} {...props}>
            {children}
          </dd>
        );
      },
      // Headings with better spacing
      h1: ({ children, ...props }: any) => {
        return (
          <h1 className={cn(
            "text-2xl font-bold text-neutral-100 mt-6 mb-4 first:mt-0",
            props.className
          )} {...props}>
            {children}
          </h1>
        );
      },
      h2: ({ children, ...props }: any) => {
        return (
          <h2 className={cn(
            "text-xl font-semibold text-neutral-100 mt-5 mb-3",
            props.className
          )} {...props}>
            {children}
          </h2>
        );
      },
      h3: ({ children, ...props }: any) => {
        return (
          <h3 className={cn(
            "text-lg font-semibold text-neutral-200 mt-4 mb-2",
            props.className
          )} {...props}>
            {children}
          </h3>
        );
      },
      // Paragraphs with better spacing
      p: ({ children, ...props }: any) => {
        return (
          <p className={cn(
            "my-3 text-neutral-300 leading-relaxed",
            props.className
          )} {...props}>
            {children}
          </p>
        );
      },
      // Strong and emphasis
      strong: ({ children, ...props }: any) => {
        return (
          <strong className={cn("font-semibold text-neutral-100", props.className)} {...props}>
            {children}
          </strong>
        );
      },
      em: ({ children, ...props }: any) => {
        return (
          <em className={cn("italic text-neutral-300", props.className)} {...props}>
            {children}
          </em>
        );
      },
      ...components,
    };
  }, [components]);

  return (
    <Streamdown
      className={cn(
        "size-full [&>*:first-child]:mt-0 [&>*:last-child]:mb-0",
        className
      )}
      components={customComponents}
      {...props}
    />
  );
}, (prevProps, nextProps) => prevProps.children === nextProps.children);

EnhancedResponse.displayName = 'EnhancedResponse';

