import { API_PREFIX, PROMPTS, PromptData } from '@/lib/consts';

describe('consts.ts', () => {
  describe('API_PREFIX', () => {
    it('should have the correct API prefix', () => {
      expect(API_PREFIX).toBe('/api/v1');
    });

    it('should be a string', () => {
      expect(typeof API_PREFIX).toBe('string');
    });

    it('should start with a slash', () => {
      expect(API_PREFIX.startsWith('/')).toBe(true);
    });
  });

  describe('PROMPTS', () => {
    it('should be an array', () => {
      expect(Array.isArray(PROMPTS)).toBe(true);
    });

    it('should not be empty', () => {
      expect(PROMPTS.length).toBeGreaterThan(0);
    });

    it('should have the expected number of prompts', () => {
      // Based on the current implementation, there are 21 prompts
      expect(PROMPTS.length).toBe(21);
    });

    describe('prompt structure validation', () => {
      it('should have all prompts with required fields', () => {
        PROMPTS.forEach((prompt, index) => {
          expect(prompt).toHaveProperty('text');
          expect(prompt).toHaveProperty('sources');
          
          expect(typeof prompt.text).toBe('string');
          expect(Array.isArray(prompt.sources)).toBe(true);
          
          // Text should not be empty
          expect(prompt.text.trim().length).toBeGreaterThan(0);
          
          // Sources should not be empty
          expect(prompt.sources.length).toBeGreaterThan(0);
        });
      });

      it('should have valid source values', () => {
        const validSources = ['ROC', 'DIANA', '3GSM'];
        
        PROMPTS.forEach((prompt) => {
          prompt.sources.forEach((source) => {
            expect(typeof source).toBe('string');
            expect(validSources).toContain(source);
          });
        });
      });

      it('should have unique prompt texts', () => {
        const texts = PROMPTS.map(prompt => prompt.text);
        const uniqueTexts = new Set(texts);
        
        expect(uniqueTexts.size).toBe(texts.length);
      });

      it('should have reasonable text lengths', () => {
        PROMPTS.forEach((prompt) => {
          // Prompts should be between 10 and 200 characters
          expect(prompt.text.length).toBeGreaterThanOrEqual(10);
          expect(prompt.text.length).toBeLessThanOrEqual(200);
        });
      });
    });

    describe('specific prompt validation', () => {
      it('should contain expected ROC prompts', () => {
        const rocPrompts = PROMPTS.filter(p => p.sources.includes('ROC'));
        expect(rocPrompts.length).toBeGreaterThan(0);
        
        // Check for some specific ROC prompts
        const rocTexts = rocPrompts.map(p => p.text);
        expect(rocTexts.some(text => text.includes('Slide2'))).toBe(true);
        expect(rocTexts.some(text => text.includes('RSWall'))).toBe(true);
      });

      it('should contain expected DIANA prompts', () => {
        const dianaPrompts = PROMPTS.filter(p => p.sources.includes('DIANA'));
        expect(dianaPrompts.length).toBeGreaterThan(0);
        
        // Check for DIANA-specific content
        const dianaTexts = dianaPrompts.map(p => p.text);
        expect(dianaTexts.some(text => text.includes('DIANA'))).toBe(true);
      });

      it('should contain expected 3GSM prompts', () => {
        const gsmPrompts = PROMPTS.filter(p => p.sources.includes('3GSM'));
        expect(gsmPrompts.length).toBeGreaterThan(0);
        
        // Check for 3GSM-specific content
        const gsmTexts = gsmPrompts.map(p => p.text);
        expect(gsmTexts.some(text => text.includes('ShapeMetriX'))).toBe(true);
      });

      it('should have prompts with multiple sources', () => {
        const multiSourcePrompts = PROMPTS.filter(p => p.sources.length > 1);
        expect(multiSourcePrompts.length).toBeGreaterThan(0);
        
        // Check for specific multi-source combinations
        const hasRocDiana = PROMPTS.some(p => 
          p.sources.includes('ROC') && p.sources.includes('DIANA')
        );
        expect(hasRocDiana).toBe(true);
      });
    });

    describe('prompt content quality', () => {
      it('should have prompts that are questions or statements', () => {
        PROMPTS.forEach((prompt) => {
          const text = prompt.text.trim();
          // Should end with ? or be a statement
          const isQuestion = text.endsWith('?');
          const isStatement = /^[A-Z]/.test(text) && text.length > 5;
          
          expect(isQuestion || isStatement).toBe(true);
        });
      });

      it('should have prompts with proper capitalization', () => {
        PROMPTS.forEach((prompt) => {
          const text = prompt.text.trim();
          // Should start with capital letter
          expect(/^[A-Z]/.test(text)).toBe(true);
        });
      });

      it('should not have prompts with excessive whitespace', () => {
        PROMPTS.forEach((prompt) => {
          // Should not start or end with whitespace
          expect(prompt.text).toBe(prompt.text.trim());
          
          // Should not have multiple consecutive spaces
          expect(prompt.text).not.toMatch(/\s{2,}/);
        });
      });
    });
  });

  describe('PromptData type', () => {
    it('should match the structure of PROMPTS items', () => {
      // This is more of a TypeScript compile-time check, 
      // but we can verify the structure at runtime
      PROMPTS.forEach((prompt) => {
        const promptData: PromptData = prompt;
        expect(promptData).toHaveProperty('text');
        expect(promptData).toHaveProperty('sources');
      });
    });
  });
});
